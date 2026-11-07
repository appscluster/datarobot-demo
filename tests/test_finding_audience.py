"""Each finding names the team the reply is for and the pipeline it came from."""
from pathlib import Path

from agent.cases import finding_context

ROOT = Path(__file__).resolve().parents[1]


def test_f101_reply_is_for_credit_risk():
    body = finding_context("F-101")
    assert body["audience"] == "Credit risk"
    assert body["pipeline"]["name"] == "scoring"
    assert "Loan model v2" in body["pipeline"]["summary"]
    assert "A-1001" in body["pipeline"]["summary"]
    assert "reply goes to the applicant" not in body["pipeline"]["summary"].lower()


def test_f102_reply_is_for_lending_ops():
    body = finding_context("F-102")
    assert body["audience"] == "Lending ops"
    assert body["pipeline"]["name"] == "intake"


def test_f106_says_nightly_scoring_has_no_owner():
    body = finding_context("F-106")
    assert body["audience"] == "Credit risk"
    assert body["pipeline"]["name"] == "scoring"
    assert "no owner" in body["pipeline"]["summary"].lower()


def test_finding_route_uses_finding_context():
    text = (ROOT / "backend" / "app.py").read_text()
    assert "finding_context" in text


def test_desk_states_the_audience():
    text = (ROOT / "frontend" / "src" / "App.tsx").read_text()
    assert "Reply for" in text
    assert "detail.audience" in text
    assert "detail.pipeline?.summary" in text
