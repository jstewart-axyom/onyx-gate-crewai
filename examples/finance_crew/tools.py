"""The finance crew's tools — plain Python, no framework imports.

``crew.py`` wraps these as CrewAI tools; ``dry_run.py`` drives them through the
framework-agnostic guard directly. ``pay_invoice`` only pretends to pay: the
point of the example is which calls the gate lets through, not the payment.
"""

from __future__ import annotations

LEDGER = [
    {"invoice_id": "INV-1041", "vendor": "initech", "amount": 1250, "due": True},
    {"invoice_id": "INV-1042", "vendor": "globex", "amount": 4800, "due": True},
    {"invoice_id": "INV-1043", "vendor": "vandelay", "amount": 12000, "due": True},
]

PAID: list[dict] = []


def read_ledger() -> str:
    """List the invoices currently due."""
    lines = ["Invoices due:"]
    for inv in LEDGER:
        if inv["due"]:
            lines.append(f"  {inv['invoice_id']}: {inv['vendor']} — ${inv['amount']}")
    return "\n".join(lines)


def pay_invoice(vendor: str, amount: int, invoice_id: str) -> str:
    """Pay a vendor invoice (simulated)."""
    PAID.append({"vendor": vendor, "amount": amount, "invoice_id": invoice_id})
    return f"Payment sent: ${amount} to {vendor} for {invoice_id}."
