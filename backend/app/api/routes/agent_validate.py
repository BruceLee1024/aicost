"""SSE streaming endpoint for the validation agent."""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Generator, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai.agents.validation_agent import (
    AgentStep,
    ValidationAgentResult,
    run_validation_agent,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])


class ValidationAgentRequest(BaseModel):
    scope: str = "full"  # "full" | "item"
    boq_item_id: Optional[int] = None
    question: str = ""


class ValidationStepOut(BaseModel):
    type: str
    content: str = ""
    tool_name: str = ""
    tool_args: dict = {}
    tool_result: str = ""


class ValidationAgentResponse(BaseModel):
    answer: str
    steps: list[ValidationStepOut]
    issues_found: int = 0
    error: str | None = None


# ── SSE streaming endpoint ──

@router.post(
    "/projects/{project_id}/agent-validate/stream",
)
def agent_validate_stream(
    project_id: int,
    payload: ValidationAgentRequest | None = None,
):
    """Run validation agent and stream steps via SSE."""
    scope = payload.scope if payload else "full"
    boq_item_id = payload.boq_item_id if payload else None
    question = payload.question if payload else ""

    step_queue: queue.Queue[AgentStep | None] = queue.Queue()
    result_holder: list[ValidationAgentResult] = []

    def on_step(step: AgentStep):
        step_queue.put(step)

    def run_agent():
        try:
            result = run_validation_agent(
                project_id=project_id,
                scope=scope,
                boq_item_id=boq_item_id,
                user_question=question,
                on_step=on_step,
            )
            result_holder.append(result)
        except Exception as exc:
            logger.error("Validation agent failed: %s", exc)
            result_holder.append(ValidationAgentResult(
                answer=f"审核Agent执行失败: {exc}",
                error="agent_error",
            ))
        finally:
            step_queue.put(None)

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    def event_stream() -> Generator[str, None, None]:
        while True:
            step = step_queue.get()
            if step is None:
                if result_holder:
                    r = result_holder[0]
                    final = {
                        "type": "done",
                        "answer": r.answer,
                        "issues_found": r.issues_found,
                        "error": r.error,
                    }
                    yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
                break

            data = {
                "type": step.type,
                "content": step.content,
                "tool_name": step.tool_name,
                "tool_args": step.tool_args,
                "tool_result": step.tool_result,
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Non-streaming endpoint ──

@router.post(
    "/projects/{project_id}/agent-validate",
    response_model=ValidationAgentResponse,
)
def agent_validate(
    project_id: int,
    payload: ValidationAgentRequest | None = None,
) -> ValidationAgentResponse:
    """Run validation agent (non-streaming)."""
    scope = payload.scope if payload else "full"
    boq_item_id = payload.boq_item_id if payload else None
    question = payload.question if payload else ""

    result = run_validation_agent(
        project_id=project_id,
        scope=scope,
        boq_item_id=boq_item_id,
        user_question=question,
    )
    return ValidationAgentResponse(
        answer=result.answer,
        steps=[
            ValidationStepOut(
                type=s.type,
                content=s.content,
                tool_name=s.tool_name,
                tool_args=s.tool_args,
                tool_result=s.tool_result,
            )
            for s in result.steps
        ],
        issues_found=result.issues_found,
        error=result.error,
    )
