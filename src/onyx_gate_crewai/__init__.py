"""Onyx Gate for CrewAI — a verifiable authorization gate for crew tool calls.

Core (no dependencies beyond the standard library):

* :class:`OnyxGate` — HTTP client for a running Onyx gateway.
* :class:`ToolGuard` — framework-agnostic per-agent guard (enforce/observe,
  fail-closed error handling, deny messages the agent can act on).

CrewAI adapter (requires ``crewai``; imported lazily):

* :func:`guard_tool` / :func:`guard_tools` — wrap tools so every execution is
  decided by the gateway before it runs.
"""

from .client import GateDecision, OnyxGate, OnyxGateError
from .guard import GateResult, ToolGuard

__all__ = [
    "GateDecision",
    "GateResult",
    "OnyxGate",
    "OnyxGateError",
    "ToolGuard",
    "guard_tool",
    "guard_tools",
    "OnyxGuardedTool",
]

__version__ = "0.2.0"


def __getattr__(name: str):
    # The CrewAI adapter is imported lazily so the core client/guard work in
    # environments without crewai installed (tests, other-framework adapters).
    if name in ("guard_tool", "guard_tools", "OnyxGuardedTool"):
        from . import crew

        return getattr(crew, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
