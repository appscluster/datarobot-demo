"""Asking to put v3 live leaves Loan model v2 in place."""
from pathlib import Path

from agent.promotion import request_promotion
from agent.scoring import load_scoring

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "scoring_state.json"


def test_promotion_does_not_change_the_live_scorer():
    before = load_scoring(str(STATE))
    raw = STATE.read_text()
    after, reason = request_promotion(before, "analyst:demo-1")
    assert after.live_model == "Loan model v2"
    assert reason == "promotion_refused"
    assert after is not before
    assert STATE.read_text() == raw


def test_shutdown_control_uses_the_promotion_refusal():
    text = (ROOT / "backend" / "app.py").read_text()
    assert "request_promotion" in text
