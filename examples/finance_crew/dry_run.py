"""Drive the finance crew's tool calls through a REAL Onyx gateway — no LLM.

This script makes exactly the calls an accounts-payable agent would make
("read the ledger, then pay every invoice that is due") through the same
:class:`ToolGuard` the CrewAI wrapper uses, so you can watch the gate work
deterministically without an LLM key.

Start the gateway first (from the Onyx engine)::

    eg_gateway --policies examples/finance_crew/policy.cedar --log trail.jsonl

then::

    python examples/finance_crew/dry_run.py [--certify]

and re-check the decision trail afterwards::

    eg_verify --audit-log trail.jsonl
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import tools  # noqa: E402

from onyx_gate_crewai import OnyxGate, ToolGuard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default=os.environ.get("ONYX_GATE_URL", "http://127.0.0.1:8080")
    )
    parser.add_argument(
        "--certify",
        action="store_true",
        help="request a kernel-re-checkable certificate with each decision",
    )
    parser.add_argument(
        "--observe", action="store_true", help="observe mode: never block, only annotate"
    )
    args = parser.parse_args()

    gate = OnyxGate(args.url)
    if not gate.health():
        print(f"No gateway answering at {args.url} — start eg_gateway first (see --help).")
        return 2
    guard = ToolGuard(
        gate,
        agent="ap-clerk",
        mode="observe" if args.observe else "enforce",
        certify=args.certify,
    )

    def call(tool_name, fn, **call_args):
        started = time.perf_counter()
        result = guard.check(tool_name, call_args)
        elapsed_ms = (time.perf_counter() - started) * 1000
        verdict = "ALLOW" if (result.decision and result.decision.allowed) else "DENY "
        if result.error:
            verdict = "ERROR"
        certified = bool(result.decision and result.decision.certificate)
        note = "  [certificate attached]" if certified else ""
        print(f"[gate {elapsed_ms:6.1f} ms] {verdict} {tool_name} {call_args or ''}{note}")
        if not result.allowed:
            print("--- the agent sees " + "-" * 40)
            print(result.blocked_message)
            print("-" * 59)
            return None
        output = fn(**call_args)
        if result.advisory_note:
            output += "\n" + result.advisory_note
        return output

    print(f"gateway: {args.url}   mode: {guard.mode}   agent: {guard.agent}\n")

    ledger = call("read_ledger", tools.read_ledger)
    print(ledger, "\n")

    for inv in tools.LEDGER:
        if not inv["due"]:
            continue
        out = call(
            "pay_invoice",
            tools.pay_invoice,
            vendor=inv["vendor"],
            amount=inv["amount"],
            invoice_id=inv["invoice_id"],
        )
        if out:
            print(out)
        print()

    paid = ", ".join(f"{p['vendor']} (${p['amount']})" for p in tools.PAID) or "none"
    print(f"Executed payments: {paid}")
    print("Every decision above — allows and denies — is now in the gateway's")
    print("hash-chained trail if it was started with --log. Re-check it with:")
    print("  eg_verify --audit-log trail.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
