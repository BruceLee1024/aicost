"""ToolDef — typed tool definitions with rich metadata.

Inspired by Claude Code's Tool type, each tool carries:
- name, description, parameter schema
- read_only / destructive / concurrency_safe flags
- execute function with AgentContext injection

Usage:
    @tool(
        name="search_quotas",
        description="搜索定额库",
        read_only=True,
    )
    def search_quotas(ctx: AgentContext, *, keyword: str, top_n: int = 10) -> str:
        ...
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TYPE_CHECKING, get_type_hints

if TYPE_CHECKING:
    from app.ai.framework.context import AgentContext

logger = logging.getLogger(__name__)

# Python type → JSON Schema type mapping
_PY_TO_JSON_TYPE: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _value_matches_json_type(value: Any, json_type: str) -> bool:
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "boolean":
        return isinstance(value, bool)
    return True


class HookAction(str, Enum):
    """Action a hook can request."""
    CONTINUE = "continue"   # proceed normally
    BLOCK = "block"         # stop tool execution, return message to LLM
    MODIFY = "modify"       # modify tool args before execution


@dataclass
class HookResult:
    """Result returned by a pre/post tool hook."""
    action: HookAction = HookAction.CONTINUE
    message: str = ""
    modified_args: dict[str, Any] | None = None  # for MODIFY action


@dataclass
class ParamDef:
    """Schema for a single tool parameter."""
    name: str
    json_type: str  # "string" | "integer" | "number" | "boolean"
    description: str = ""
    required: bool = True
    default: Any = None
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ToolDef:
    """A tool definition with metadata, schema, and execution function.

    Mirrors Claude Code's Tool type but adapted for Python / our domain.
    """
    name: str
    description: str
    parameters: list[ParamDef] = field(default_factory=list)
    func: Callable[..., str] | None = None

    # ── Metadata flags (borrowed from Claude Code) ──
    read_only: bool = False
    destructive: bool = False
    concurrency_safe: bool | None = None  # None → auto from read_only
    requires_confirmation: bool = False  # HITL gate

    # ── Hook system (F3) ──
    pre_hooks: list[Callable] = field(default_factory=list)
    post_hooks: list[Callable] = field(default_factory=list)

    @property
    def is_concurrency_safe(self) -> bool:
        if self.concurrency_safe is not None:
            return self.concurrency_safe
        return self.read_only

    # ── OpenAI function calling schema ──

    def to_openai_schema(self) -> dict[str, Any]:
        """Generate OpenAI-compatible function calling schema."""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self._effective_parameters():
            prop: dict[str, Any] = {"type": p.json_type}
            description = p.description
            if p.aliases:
                alias_text = f"兼容别名: {', '.join(p.aliases)}"
                description = f"{description} {alias_text}".strip()
            if description:
                prop["description"] = description
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }
        if required:
            schema["function"]["parameters"]["required"] = required
        return schema

    # ── Execution ──

    def execute(self, ctx: "AgentContext", args: dict[str, Any]) -> str:
        """Execute the tool with context injection and hook support (F3).

        Lifecycle: pre_hooks → func() → post_hooks.
        Pre-hooks can block execution or modify args.
        Post-hooks can observe or transform the output.
        """
        if self.func is None:
            return self._error_payload(
                error_type="execution_error",
                error=f"Tool '{self.name}' has no implementation",
                recoverable=False,
            )

        if not isinstance(args, dict):
            return self._validation_error_payload(
                missing_required=[],
                unexpected_params=[],
                type_mismatches=[{
                    "param": "arguments",
                    "expected": "object",
                    "received": type(args).__name__,
                }],
            )

        # ── Pre-hooks ──
        effective_args = dict(args)
        for hook in self.pre_hooks:
            try:
                hr = hook(ctx, self.name, effective_args)
                if isinstance(hr, HookResult):
                    if hr.action == HookAction.BLOCK:
                        logger.info("Pre-hook blocked tool '%s': %s", self.name, hr.message)
                        return json.dumps({"blocked": True, "reason": hr.message}, ensure_ascii=False)
                    if hr.action == HookAction.MODIFY and hr.modified_args:
                        effective_args.update(hr.modified_args)
            except Exception as exc:
                logger.warning("Pre-hook for tool '%s' failed: %s", self.name, exc)

        effective_params = self._effective_parameters()
        effective_args = self._normalize_args(effective_args, effective_params)
        missing_required = [
            p.name
            for p in effective_params
            if p.required and (p.name not in effective_args or effective_args[p.name] is None)
        ]
        unexpected_params = []
        if not self._accepts_var_keyword():
            recognized_names = self._recognized_param_names(effective_params)
            unexpected_params = sorted(
                key for key in args.keys() if key not in recognized_names
            )
        type_mismatches = []
        for p in effective_params:
            if p.name not in effective_args or effective_args[p.name] is None:
                continue
            value = effective_args[p.name]
            if not _value_matches_json_type(value, p.json_type):
                type_mismatches.append({
                    "param": p.name,
                    "expected": p.json_type,
                    "received": type(value).__name__,
                })

        if missing_required or unexpected_params or type_mismatches:
            return self._validation_error_payload(
                missing_required=missing_required,
                unexpected_params=unexpected_params,
                type_mismatches=type_mismatches,
            )

        # ── Execute ──
        try:
            output = self.func(ctx, **effective_args)
        except Exception as exc:
            logger.error("Tool %s execution failed: %s", self.name, exc, exc_info=True)
            output = self._error_payload(
                error_type="execution_error",
                error=f"工具执行失败: {exc}",
                recoverable=False,
            )

        # ── Post-hooks ──
        for hook in self.post_hooks:
            try:
                hr = hook(ctx, self.name, effective_args, output)
                if isinstance(hr, HookResult) and hr.message:
                    # Append hook message to output
                    try:
                        data = json.loads(output)
                        if isinstance(data, dict):
                            data["_hook_note"] = hr.message
                            output = json.dumps(data, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        output = output + f"\n[Hook] {hr.message}"
            except Exception as exc:
                logger.warning("Post-hook for tool '%s' failed: %s", self.name, exc)

        return output

    def _accepts_var_keyword(self) -> bool:
        if self.func is None:
            return False
        try:
            sig = inspect.signature(self.func)
        except (TypeError, ValueError):
            return False
        return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

    def _effective_parameters(self) -> list[ParamDef]:
        if self.parameters:
            return self.parameters
        if self.func is None:
            return []
        return _extract_params(self.func)

    def _recognized_param_names(self, parameters: list[ParamDef]) -> set[str]:
        names: set[str] = set()
        for p in parameters:
            names.add(p.name)
            names.update(p.aliases)
        return names

    def _normalize_args(self, args: dict[str, Any], parameters: list[ParamDef]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        recognized_names = self._recognized_param_names(parameters)
        for p in parameters:
            if p.name in args:
                normalized[p.name] = args[p.name]
                continue
            for alias in p.aliases:
                if alias in args:
                    normalized[p.name] = args[alias]
                    break
        if self._accepts_var_keyword():
            for key, value in args.items():
                if key not in recognized_names:
                    normalized[key] = value
        return normalized

    @staticmethod
    def _example_value_for_param(param: ParamDef) -> Any:
        if param.name in {"query", "task", "instruction"}:
            return "<请填写当前任务、问题或检索语句>"
        if param.name == "scope":
            return "project"
        if param.json_type == "string":
            return f"<{param.name}>"
        if param.json_type == "integer":
            return param.default if isinstance(param.default, int) else 1
        if param.json_type == "number":
            if isinstance(param.default, (int, float)) and not isinstance(param.default, bool):
                return param.default
            return 0.0
        if param.json_type == "boolean":
            return param.default if isinstance(param.default, bool) else False
        return f"<{param.name}>"

    def _suggested_args(self, parameters: list[ParamDef]) -> dict[str, Any]:
        suggested: dict[str, Any] = {}
        for p in parameters:
            if p.required:
                suggested[p.name] = self._example_value_for_param(p)
        for p in parameters:
            if p.required or p.default is None:
                continue
            suggested[p.name] = p.default
        return suggested

    def _validation_error_payload(
        self,
        *,
        missing_required: list[str],
        unexpected_params: list[str],
        type_mismatches: list[dict[str, str]],
    ) -> str:
        issues: list[str] = []
        for param in missing_required:
            issues.append(f"缺少必填参数 `{param}`")
        for param in unexpected_params:
            issues.append(f"包含未定义参数 `{param}`")
        for mismatch in type_mismatches:
            issues.append(
                f"参数 `{mismatch['param']}` 类型应为 `{mismatch['expected']}`，实际为 `{mismatch['received']}`"
            )

        error = (
            f"工具 `{self.name}` 参数校验失败：" + "；".join(issues)
            if issues else f"工具 `{self.name}` 参数校验失败"
        )
        effective_params = self._effective_parameters()
        details: dict[str, Any] = {
            "accepted_params": [p.name for p in effective_params],
            "suggested_args": self._suggested_args(effective_params),
        }
        param_descriptions = {
            p.name: p.description
            for p in effective_params
            if p.description
        }
        if param_descriptions:
            details["param_descriptions"] = param_descriptions
        if missing_required:
            details["missing_required"] = missing_required
        if unexpected_params:
            details["unexpected_params"] = unexpected_params
        if type_mismatches:
            details["type_mismatches"] = type_mismatches

        return self._error_payload(
            error_type="validation_error",
            error=error,
            recoverable=True,
            retry_hint="请按 suggested_args 的结构补全或修正参数后重试，不要空参调用。",
            details=details,
        )

    def _error_payload(
        self,
        *,
        error_type: str,
        error: str,
        recoverable: bool,
        retry_hint: str = "",
        details: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "ok": False,
            "error_type": error_type,
            "error": error,
            "recoverable": recoverable,
            "tool_name": self.name,
        }
        if retry_hint:
            payload["retry_hint"] = retry_hint
        if details:
            payload["details"] = details
        return json.dumps(payload, ensure_ascii=False)


def _extract_params(func: Callable) -> list[ParamDef]:
    """Auto-extract ParamDef list from function signature + type hints.

    Skips the first parameter (assumed to be ``ctx: AgentContext``).
    """
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    params: list[ParamDef] = []
    skip_first = True
    for pname, p in sig.parameters.items():
        # Skip 'self', 'cls', and the first positional arg (ctx)
        if pname in ("self", "cls"):
            continue
        if skip_first:
            skip_first = False
            continue
        # Skip **kwargs, *args
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue

        has_default = p.default is not inspect.Parameter.empty
        py_type = hints.get(pname, None)
        if py_type is None:
            # Infer from default value when no annotation is present
            if has_default and p.default is not None and not isinstance(p.default, bool):
                py_type = type(p.default)
            else:
                py_type = str
        # Handle Optional[X] → X
        origin = getattr(py_type, "__origin__", None)
        if origin is not None:
            hint_args = getattr(py_type, "__args__", ())
            if hint_args:
                py_type = hint_args[0]

        json_type = _PY_TO_JSON_TYPE.get(py_type, "string")
        params.append(ParamDef(
            name=pname,
            json_type=json_type,
            required=not has_default,
            default=p.default if has_default else None,
        ))
    return params


def tool(
    *,
    name: str,
    description: str,
    read_only: bool = False,
    destructive: bool = False,
    concurrency_safe: bool | None = None,
    requires_confirmation: bool = False,
    params: list[ParamDef] | None = None,
) -> Callable[[Callable[..., str]], ToolDef]:
    """Decorator to create a ToolDef from a function.

    Usage::

        @tool(name="search_quotas", description="搜索定额库", read_only=True)
        def search_quotas(ctx: AgentContext, *, keyword: str, top_n: int = 10) -> str:
            ...

    The decorated name becomes a ToolDef instance (not the original function).
    """
    def decorator(func: Callable[..., str]) -> ToolDef:
        resolved_params = params if params is not None else _extract_params(func)
        return ToolDef(
            name=name,
            description=description,
            parameters=resolved_params,
            func=func,
            read_only=read_only,
            destructive=destructive,
            concurrency_safe=concurrency_safe,
            requires_confirmation=requires_confirmation,
        )
    return decorator


def pre_hook(tool_def: ToolDef) -> Callable:
    """Decorator to register a pre-execution hook on a ToolDef.

    Usage::

        @pre_hook(bind_quota_tool)
        def check_existing_binding(ctx, tool_name, args):
            # Return HookResult to block or modify
            return HookResult(action=HookAction.CONTINUE)
    """
    def decorator(func: Callable) -> Callable:
        tool_def.pre_hooks.append(func)
        return func
    return decorator


def post_hook(tool_def: ToolDef) -> Callable:
    """Decorator to register a post-execution hook on a ToolDef.

    Usage::

        @post_hook(bind_quota_tool)
        def auto_recalculate(ctx, tool_name, args, output):
            # side effects after tool execution
            return HookResult(message="已自动重算")
    """
    def decorator(func: Callable) -> Callable:
        tool_def.post_hooks.append(func)
        return func
    return decorator
