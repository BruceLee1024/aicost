"""SSE streaming endpoint for the valuation agent.

Streams agent steps (thinking, tool_call, tool_result, answer) as
Server-Sent Events so the frontend can display them in real-time.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Generator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai.agents.valuation_agent import AgentResult, AgentStep, run_valuation_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])


class AgentValuateRequest(BaseModel):
    instruction: str = ""


class AgentStepOut(BaseModel):
    type: str
    content: str = ""
    tool_name: str = ""
    tool_args: dict = {}
    tool_result: str = ""


class AgentValuateResponse(BaseModel):
    answer: str
    steps: list[AgentStepOut]
    bindings_changed: bool = False
    error: str | None = None


# ── SSE streaming endpoint ──────────────────────────────────────

@router.post(
    "/projects/{project_id}/boq-items/{boq_item_id}/agent-valuate/stream",
)
def agent_valuate_stream(
    project_id: int,
    boq_item_id: int,
    payload: AgentValuateRequest | None = None,
):
    """Run valuation agent and stream steps via SSE."""
    instruction = payload.instruction if payload else ""

    step_queue: queue.Queue[AgentStep | None] = queue.Queue()
    result_holder: list[AgentResult] = []

    def on_step(step: AgentStep):
        step_queue.put(step)

    def run_agent():
        try:
            result = run_valuation_agent(
                project_id=project_id,
                boq_item_id=boq_item_id,
                user_instruction=instruction,
                on_step=on_step,
            )
            result_holder.append(result)
        except Exception as exc:
            logger.error("Agent run failed: %s", exc)
            result_holder.append(AgentResult(
                answer=f"Agent 执行失败: {exc}",
                error="agent_error",
            ))
        finally:
            step_queue.put(None)  # sentinel

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    def event_stream() -> Generator[str, None, None]:
        while True:
            step = step_queue.get()
            if step is None:
                # Send final result
                if result_holder:
                    r = result_holder[0]
                    final = {
                        "type": "done",
                        "answer": r.answer,
                        "bindings_changed": r.bindings_changed,
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


# ── Non-streaming endpoint (fallback) ──────────────────────────

@router.post(
    "/projects/{project_id}/boq-items/{boq_item_id}/agent-valuate",
    response_model=AgentValuateResponse,
)
def agent_valuate(
    project_id: int,
    boq_item_id: int,
    payload: AgentValuateRequest | None = None,
) -> AgentValuateResponse:
    """Run valuation agent (non-streaming) and return full result."""
    instruction = payload.instruction if payload else ""
    result = run_valuation_agent(
        project_id=project_id,
        boq_item_id=boq_item_id,
        user_instruction=instruction,
    )
    return AgentValuateResponse(
        answer=result.answer,
        steps=[
            AgentStepOut(
                type=s.type,
                content=s.content,
                tool_name=s.tool_name,
                tool_args=s.tool_args,
                tool_result=s.tool_result,
            )
            for s in result.steps
        ],
        bindings_changed=result.bindings_changed,
        error=result.error,
    )
