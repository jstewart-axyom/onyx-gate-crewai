import pytest

from onyx_gate_crewai import OnyxGate, OnyxGateError
from tests.stub_gateway import StubGateway


def test_allow_decision_parses():
    with StubGateway(lambda p: (200, {"decision": "allow", "policy_version": "v1"})) as stub:
        d = OnyxGate(stub.url).gate_tool_call(agent="a", tool="read_ledger")
        assert d.allowed
        assert d.decision == "allow"
        assert d.policy_version == "v1"
        assert d.explanation is None
        sent = stub.requests[0]
        assert sent["path"] == "/gate/tool-call"
        assert sent["payload"]["agent"] == "a"
        assert sent["payload"]["tool"] == "read_ledger"
        assert sent["payload"]["resource"] == 'Tool::"read_ledger"'


def test_deny_carries_explanation():
    body = {"decision": "deny", "explanation": "no permit matched"}
    with StubGateway(lambda p: (200, body)) as stub:
        d = OnyxGate(stub.url).gate_tool_call(agent="a", tool="pay_invoice")
        assert not d.allowed
        assert d.explanation == "no permit matched"


def test_attrs_parents_context_and_certify_are_sent():
    with StubGateway() as stub:
        OnyxGate(stub.url).gate_tool_call(
            agent="a",
            tool="t",
            resource_attrs={"amount": 4800, "vendor": "globex", "urgent": True},
            resource_parents=['Group::"finance"'],
            context={"env": "prod"},
            certify=True,
        )
        sent = stub.requests[0]
        assert sent["path"] == "/gate/tool-call?certify=true"
        assert sent["payload"]["resource_attrs"] == {
            "amount": 4800,
            "vendor": "globex",
            "urgent": True,
        }
        assert sent["payload"]["resource_parents"] == ['Group::"finance"']
        assert sent["payload"]["context"] == {"env": "prod"}


def test_bearer_key_is_presented():
    with StubGateway(require_bearer="sekrit") as stub:
        gate = OnyxGate(stub.url, api_key="sekrit")
        assert gate.gate_tool_call(agent="a", tool="t").allowed
        assert stub.requests[0]["authorization"] == "Bearer sekrit"


def test_wrong_bearer_key_raises():
    with StubGateway(require_bearer="sekrit") as stub:
        with pytest.raises(OnyxGateError, match="401"):
            OnyxGate(stub.url, api_key="wrong").gate_tool_call(agent="a", tool="t")


def test_http_error_raises():
    with StubGateway(lambda p: (400, {"error": "bad"})) as stub:
        with pytest.raises(OnyxGateError, match="400"):
            OnyxGate(stub.url).gate_tool_call(agent="a", tool="t")


def test_unreachable_gateway_raises():
    with pytest.raises(OnyxGateError, match="unreachable"):
        OnyxGate("http://127.0.0.1:1", timeout=0.5).gate_tool_call(agent="a", tool="t")


def test_unrecognized_decision_raises():
    with StubGateway(lambda p: (200, {"decision": "maybe"})) as stub:
        with pytest.raises(OnyxGateError, match="unrecognized"):
            OnyxGate(stub.url).gate_tool_call(agent="a", tool="t")


def test_uid_unsafe_tool_name_is_refused_client_side():
    # A quote could change what the server parses out of the resource uid
    # string — the client refuses instead of escaping (fail-closed upstream).
    gate = OnyxGate("http://127.0.0.1:1")
    with pytest.raises(OnyxGateError, match="entity id"):
        gate.gate_tool_call(agent="a", tool='evil"tool')
    with pytest.raises(OnyxGateError, match="non-empty"):
        gate.gate_tool_call(agent="", tool="t")


def test_health():
    with StubGateway() as stub:
        assert OnyxGate(stub.url).health()
    assert not OnyxGate("http://127.0.0.1:1", timeout=0.5).health()
