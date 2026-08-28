"""CrewAI adapter — wrap a crew's tools so every execution passes the gate.

Usage::

    from crewai import Agent
    from onyx_gate_crewai import OnyxGate, ToolGuard, guard_tools

    gate = OnyxGate("http://127.0.0.1:8080")
    guard = ToolGuard(gate, agent="ap-clerk")          # one guard per agent identity

    clerk = Agent(
        role="Accounts-payable clerk",
        goal="Pay the invoices that are due",
        backstory="...",
        tools=guard_tools([read_ledger, pay_invoice], guard=guard),
    )

The wrapper is *permissionless*: it needs no change to CrewAI and no change to
the wrapped tools. Each guarded tool keeps the inner tool's name, description,
and argument schema (the LLM sees an identical tool), but its ``_run`` consults
the gateway first. A denied call never executes — the agent receives the deny
message, including which call was blocked and the policy's reason, as the tool
observation, and re-plans from there.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from pydantic import PrivateAttr

from .client import OnyxGate
from .guard import ToolGuard

try:  # CrewAI >= 0.60 exposes BaseTool here.
    from crewai.tools import BaseTool
except ImportError:  # pragma: no cover - older layouts
    from crewai.tools.base_tool import BaseTool  # type: ignore[no-redef]


class OnyxGuardedTool(BaseTool):
    """A CrewAI tool whose every execution is decided by an Onyx gateway."""

    _inner: BaseTool = PrivateAttr()
    _guard: ToolGuard = PrivateAttr()

    def __init__(self, inner: BaseTool, guard: ToolGuard, **kwargs: Any) -> None:
        fields: dict[str, Any] = {
            "name": inner.name,
            "description": inner.description,
        }
        # Preserve the inner tool's LLM-facing schema and result handling when
        # present, so guarding a tool is invisible to the agent's planner.
        args_schema = getattr(inner, "args_schema", None)
        if args_schema is not None:
            fields["args_schema"] = args_schema
        for passthrough in ("result_as_answer", "cache_function"):
            value = getattr(inner, passthrough, None)
            if value is not None:
                fields[passthrough] = value
        fields.update(kwargs)
        super().__init__(**fields)
        self._inner = inner
        self._guard = guard

    def _named_args(self, args: tuple, kwargs: dict) -> dict[str, Any]:
        """Best-effort naming of positional args via the schema field order."""
        named = dict(kwargs)
        if args:
            schema = getattr(self, "args_schema", None)
            field_names = list(getattr(schema, "model_fields", {}).keys()) if schema else []
            for i, value in enumerate(args):
                key = field_names[i] if i < len(field_names) else f"arg{i}"
                named.setdefault(key, value)
        return named

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        result = self._guard.check(self.name, self._named_args(args, kwargs))
        if not result.allowed:
            return result.blocked_message
        output = self._inner._run(*args, **kwargs)
        if result.advisory_note:
            return f"{output}\n\n{result.advisory_note}"
        return output


def guard_tool(
    tool: BaseTool,
    guard: Optional[ToolGuard] = None,
    gate: Optional[OnyxGate] = None,
    **guard_kwargs: Any,
) -> OnyxGuardedTool:
    """Wrap one CrewAI tool. Pass a shared ``guard``, or gate/guard kwargs."""
    if guard is None:
        guard = ToolGuard(gate=gate, **guard_kwargs)
    return OnyxGuardedTool(tool, guard)


def guard_tools(
    tools: Iterable[BaseTool],
    guard: Optional[ToolGuard] = None,
    gate: Optional[OnyxGate] = None,
    **guard_kwargs: Any,
) -> list[OnyxGuardedTool]:
    """Wrap an agent's tool list with one shared guard (one agent identity)."""
    if guard is None:
        guard = ToolGuard(gate=gate, **guard_kwargs)
    return [OnyxGuardedTool(tool, guard) for tool in tools]
