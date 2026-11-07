"""A decision stays on the desk. It is not sent to an applicant or the bank."""
from pathlib import Path

from agent.delivery import deliver, note_for_guard

ROOT = Path(__file__).resolve().parents[1]


def test_approve_stays_with_credit_risk_and_is_not_sent():
    item = deliver("approve", "Credit risk", True)
    assert item.queue == "Credit risk" and item.sent is False
    assert item.note == "Recorded for Credit risk. Nothing was sent."


def test_escalate_without_draft_goes_to_pod_lead():
    item = deliver("escalate", "Credit risk", False)
    assert item.queue == "Pod lead" and item.sent is False
    assert "applicant" not in item.note.lower()
    assert item.note == "Escalated to the pod lead. Nothing was sent."


def test_reject_returns_to_the_analyst():
    item = deliver("reject", "Lending ops", True)
    assert item.queue == "Analyst"
    assert item.note == "Returned to the analyst for rework."


def test_caller_note_reaches_the_guard():
    text = note_for_guard("shut down the model", "Recorded for Credit risk. Nothing was sent.")
    assert "shut down" in text
    assert "Recorded for Credit risk" in text
    route = (ROOT / "backend" / "app.py").read_text()
    assert "note_for_guard" in route


def test_decision_route_uses_deliver():
    text = (ROOT / "backend" / "app.py").read_text()
    assert "deliver(" in text


def test_desk_shows_the_delivery_note():
    text = (ROOT / "frontend" / "src" / "App.tsx").read_text()
    assert "delivery?.note" in text or "delivery.note" in text
