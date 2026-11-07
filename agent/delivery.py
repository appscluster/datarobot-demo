"""Where a human decision goes. Nothing is sent."""
from dataclasses import dataclass


@dataclass
class Delivery:
    queue: str
    sent: bool
    note: str


def note_for_guard(caller_note: str, delivery_note: str) -> str:
    return f"{caller_note} {delivery_note}".strip()


def deliver(decision: str, audience: str, draft_ready: bool) -> Delivery:
    choice = decision.lower()
    if choice == "approve":
        return Delivery(audience, False, f"Recorded for {audience}. Nothing was sent.")
    if choice == "escalate":
        return Delivery("Pod lead", False, "Escalated to the pod lead. Nothing was sent.")
    if choice == "reject":
        return Delivery("Analyst", False, "Returned to the analyst for rework.")
    raise ValueError(f"unknown decision: {decision}")
