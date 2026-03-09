"""Project-aware chat agent with tool calling for action-capable assistant.

Capabilities:
- Answer questions about the project (BOQ, bindings, costs)
- Search BOQ items by keyword
- View binding details for a BOQ item
- Trigger calculation for the project
- Provide cost analysis and insights
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.ai.prompts import load_prompt
from app.ai.providers import AIProviderError, get_ai_provider

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "你是工程计价项目的 AI 助手。你可以回答关于项目清单、定额绑定、计算结果的问题，"
    "也可以执行操作如搜索清单、查看绑定、触发计算等。请用中文简洁回答。"
)

# Tool definitions for action-capable chat
_CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_boq",
            "description": "在当前项目的清单中搜索条目，按名称或编码关键词匹配。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_bindings",
            "description": "查看指定清单项的定额绑定详情。",
            "parameters": {
                "type": "object",
                "properties": {
                    "boq_item_id": {"type": "integer", "description": "清单项ID"},
                },
                "required": ["boq_item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_stats",
            "description": "获取项目统计信息：清单总数、绑定覆盖率、计算汇总等。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def chat_with_project_context(
    *,
    message: str,
    history: list[dict[str, str]],
    project_summary: dict[str, Any],
    project_id: int | None = None,
) -> str | None:
    """Generate a chat response with project context and optional tool calling.

    Returns None if AI is not available.
    """
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return None

    try:
        system_prompt = load_prompt("chat_system.txt")
    except OSError:
        system_prompt = _DEFAULT_SYSTEM_PROMPT

    # Inject project summary into system prompt
    summary_text = json.dumps(project_summary, ensure_ascii=False, indent=2)
    full_system = f"{system_prompt}\n\n当前项目数据摘要：\n{summary_text}"

    # Build message list: system + history + current message
    messages: list[dict[str, Any]] = [{"role": "system", "content": full_system}]
    for h in history[-10:]:  # Keep last 10 turns
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": message})

    # Try tool-calling path first if project_id is available
    if project_id:
        try:
            response = provider.generate_with_tools(
                task="chat",
                messages=messages,
                tools=_CHAT_TOOLS,
            )

            # If tool calls requested, execute them and get final answer
            if response["tool_calls"]:
                return _handle_tool_calls(
                    provider=provider,
                    messages=messages,
                    tool_calls=response["tool_calls"],
                    initial_content=response["content"],
                    project_id=project_id,
                )

            # No tool calls, just return the text
            if response["content"]:
                return response["content"]
        except AIProviderError:
            pass  # Fall through to simple text generation

    # Fallback: simple text generation
    try:
        return provider.generate_text(
            task="chat",
            messages=messages,  # type: ignore[arg-type]
        )
    except AIProviderError:
        return None


def _handle_tool_calls(
    *,
    provider: Any,
    messages: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    initial_content: str | None,
    project_id: int,
) -> str | None:
    """Execute tool calls and get the final response."""
    from app.db.session import get_db

    db: Session = next(get_db())
    try:
        # Add assistant message with tool calls
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": initial_content or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ],
        }
        messages.append(assistant_msg)

        # Execute each tool
        for tc in tool_calls:
            result = _execute_chat_tool(db, project_id, tc["name"], tc["arguments"])
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        # Get final answer
        final = provider.generate_with_tools(
            task="chat",
            messages=messages,
            tools=_CHAT_TOOLS,
        )
        return final["content"] or "操作已完成。"
    except Exception as exc:
        logger.warning("Chat tool execution failed: %s", exc)
        return None
    finally:
        db.close()


def _execute_chat_tool(
    db: Session, project_id: int, tool_name: str, args: dict[str, Any],
) -> str:
    """Execute a chat tool and return JSON result."""
    from app.models.boq_item import BoqItem
    from app.models.line_item_quota_binding import LineItemQuotaBinding
    from app.models.quota_item import QuotaItem
    from app.models.calc_result import CalcResult

    try:
        if tool_name == "search_boq":
            keyword = args.get("keyword", "")
            items = db.query(BoqItem).filter(
                BoqItem.project_id == project_id,
            ).all()
            matched = [
                {"id": i.id, "code": i.code, "name": i.name, "unit": i.unit, "quantity": i.quantity, "division": i.division}
                for i in items
                if keyword.lower() in (i.name or "").lower() or keyword.lower() in (i.code or "").lower()
            ][:20]
            return json.dumps({"results": matched, "total": len(matched)}, ensure_ascii=False)

        elif tool_name == "view_bindings":
            boq_item_id = args.get("boq_item_id", 0)
            bindings = (
                db.query(LineItemQuotaBinding)
                .filter(LineItemQuotaBinding.boq_item_id == boq_item_id)
                .all()
            )
            result = []
            for b in bindings:
                q = db.query(QuotaItem).filter(QuotaItem.id == b.quota_item_id).first()
                result.append({
                    "binding_id": b.id,
                    "quota_code": q.quota_code if q else "?",
                    "quota_name": q.name if q else "?",
                    "coefficient": b.coefficient,
                })
            return json.dumps({"bindings": result}, ensure_ascii=False)

        elif tool_name == "get_project_stats":
            items = db.query(BoqItem).filter(BoqItem.project_id == project_id).all()
            boq_ids = [i.id for i in items]
            bound_ids = set()
            if boq_ids:
                bound_ids = {
                    r.boq_item_id
                    for r in db.query(LineItemQuotaBinding)
                    .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
                    .all()
                }
            calc_results = (
                db.query(CalcResult).filter(CalcResult.boq_item_id.in_(boq_ids)).all()
                if boq_ids else []
            )
            return json.dumps({
                "boq_count": len(items),
                "bound_count": len(bound_ids),
                "unbound_count": len(items) - len(bound_ids),
                "binding_rate": f"{len(bound_ids)/len(items)*100:.1f}%" if items else "0%",
                "calc_total": round(sum(c.total_cost for c in calc_results), 2),
            }, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
