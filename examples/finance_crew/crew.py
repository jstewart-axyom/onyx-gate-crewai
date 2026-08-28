"""The live CrewAI version of the finance example — one agent, guarded tools.

Needs ``pip install onyx-gate-crewai[crewai]``, an LLM key (any provider CrewAI
supports; set ``CREW_MODEL``, e.g. ``anthropic/claude-sonnet-5`` with
``ANTHROPIC_API_KEY``), and a running gateway::

    eg_gateway --policies examples/finance_crew/policy.cedar --log trail.jsonl
    python examples/finance_crew/crew.py

The agent is told to pay every invoice that is due. Two invoices are inside
the mandate and go through; the third (vandelay, $12,000) is outside it — the
gate blocks the call before it executes and the agent reads the deny reason as
its tool observation, reports the invoice as needing human approval, and moves
on. Watch the gateway's trail for the full decision record.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import tools  # noqa: E402

from crewai import Agent, Crew, Task  # noqa: E402
from crewai.tools import tool  # noqa: E402

from onyx_gate_crewai import OnyxGate, ToolGuard, guard_tools  # noqa: E402


@tool("read_ledger")
def read_ledger() -> str:
    """List the invoices currently due."""
    return tools.read_ledger()


@tool("pay_invoice")
def pay_invoice(vendor: str, amount: int, invoice_id: str) -> str:
    """Pay a vendor invoice. vendor: vendor name; amount: whole dollars; invoice_id: the ledger id."""
    return tools.pay_invoice(vendor, amount, invoice_id)


def main() -> None:
    gate = OnyxGate(os.environ.get("ONYX_GATE_URL", "http://127.0.0.1:8080"))
    if not gate.health():
        raise SystemExit("No gateway answering — start eg_gateway first (see module docstring).")
    guard = ToolGuard(gate, agent="ap-clerk")

    clerk = Agent(
        role="Accounts-payable clerk",
        goal="Settle the invoices that are due",
        backstory=(
            "You process vendor invoices. Company policy is enforced by an "
            "authorization gate outside your control: if the gate denies a "
            "payment, record the invoice as needing human approval and move on."
        ),
        tools=guard_tools([read_ledger, pay_invoice], guard=guard),
        llm=os.environ.get("CREW_MODEL", "anthropic/claude-sonnet-5"),
        verbose=True,
    )
    settle = Task(
        description=(
            "Read the ledger and pay every invoice that is due. Finish with a "
            "short report: what was paid, and what (if anything) needs human "
            "approval and why."
        ),
        expected_output="A settlement report listing payments made and items escalated.",
        agent=clerk,
    )
    result = Crew(agents=[clerk], tasks=[settle], verbose=True).kickoff()
    print("\n=== settlement report ===\n", result)
    paid = ", ".join(f"{p['vendor']} (${p['amount']})" for p in tools.PAID) or "none"
    print(f"\nPayments that actually executed: {paid}")


if __name__ == "__main__":
    main()
