"""AI Tools — extracted tool implementations for all agents.

All tools register themselves into the global ToolRegistry on import.
Import this package once at app startup to populate the registry.
"""

from app.ai.framework.tool_registry import registry

from app.ai.tools import quota_tools      # noqa: F401
from app.ai.tools import validation_tools  # noqa: F401
from app.ai.tools import chat_tools        # noqa: F401
from app.ai.tools import boq_tools         # noqa: F401
from app.ai.tools import memory_tools      # noqa: F401
from app.ai.tools import skill_tools       # noqa: F401
from app.ai.tools import project_tools     # noqa: F401
from app.ai.tools import report_tools      # noqa: F401
from app.ai.tools import rag_tools         # noqa: F401
from app.ai.tools import measure_tools     # noqa: F401
from app.ai.tools import lmm_tools         # noqa: F401
from app.ai.tools import compliance_tools  # noqa: F401


def register_all_tools() -> None:
    """Ensure all tool modules are imported and registered.

    Called once at app startup. Idempotent — re-importing is a no-op.
    """
    # The imports above already trigger registration via module-level code.
    pass


__all__ = ["registry", "register_all_tools"]
