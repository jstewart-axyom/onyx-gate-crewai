"""CrewAI adapter tests — run only when crewai is installed (the CI adapter job)."""

import pytest

crewai_tools = pytest.importorskip("crewai.tools")

from pydantic import BaseModel, Field  # noqa: E402

from onyx_gate_crewai import OnyxGate, ToolGuard, guard_tool, guard_tools  # noqa: E402
from tests.stub_gateway import StubGateway  # noqa: E402

DENY = (200, {"decision": "deny", "explanation": "vendor not on the approved ledger"})
ALLOW = (200, {"decision": "allow"})


class PayArgs(BaseModel):
    vendor: str = Field(description="Vendor to pay")
    amount: int = Field(description="Amount in whole dollars")


CALLS: list = []  # module-level: a pydantic field would be copied per instance


class PayInvoice(crewai_tools.BaseTool):
    name: str = "pay_invoice"
    description: str = "Pay a vendor invoice."
    args_schema: type[BaseModel] = PayArgs

    def _run(self, vendor: str, amount: int) -> str:
        CALLS.append((vendor, amount))
        return f"PAID {vendor} ${amount}"


def make_guarded(stub, **guard_kwargs):
    CALLS.clear()
    guard = ToolGuard(gate=OnyxGate(stub.url), agent="ap-clerk", **guard_kwargs)
    return guard_tool(PayInvoice(), guard=guard)


def test_wrapper_preserves_the_llm_facing_surface():
    with StubGateway() as stub:
        tool = make_guarded(stub)
        assert tool.name == "pay_invoice"
        assert tool.description == "Pay a vendor invoice."
        assert tool.args_schema is PayArgs


def test_allow_executes_inner_tool():
    with StubGateway(lambda p: ALLOW) as stub:
        tool = make_guarded(stub)
        out = tool.run(vendor="globex", amount=4800)
        assert out == "PAID globex $4800"
        assert CALLS == [("globex", 4800)]
        payload = stub.requests[0]["payload"]
        assert payload["resource_attrs"] == {"vendor": "globex", "amount": 4800}


def test_deny_blocks_inner_tool_and_returns_the_reason():
    with StubGateway(lambda p: DENY) as stub:
        tool = make_guarded(stub)
        out = tool.run(vendor="vandelay", amount=12000)
        assert "did NOT execute" in out
        assert "vendor not on the approved ledger" in out
        assert "pay_invoice(vendor='vandelay', amount=12000)" in out
        assert CALLS == []  # the inner tool never ran


def test_observe_mode_runs_and_annotates():
    with StubGateway(lambda p: DENY) as stub:
        tool = make_guarded(stub, mode="observe")
        out = tool.run(vendor="vandelay", amount=12000)
        assert out.startswith("PAID vandelay $12000")
        assert "would have been DENIED" in out
        assert CALLS == [("vandelay", 12000)]


def test_gateway_down_fails_closed_through_the_adapter():
    guard = ToolGuard(gate=OnyxGate("http://127.0.0.1:1", timeout=0.5), agent="a")
    CALLS.clear()
    tool = guard_tool(PayInvoice(), guard=guard)
    out = tool.run(vendor="globex", amount=1)
    assert "fail-closed" in out
    assert CALLS == []


def test_guard_tools_shares_one_guard():
    with StubGateway(lambda p: ALLOW) as stub:
        guard = ToolGuard(gate=OnyxGate(stub.url), agent="ap-clerk")
        tools = guard_tools([PayInvoice()], guard=guard)
        assert len(tools) == 1
        tools[0].run(vendor="globex", amount=1)
        assert stub.requests[0]["payload"]["agent"] == "ap-clerk"
