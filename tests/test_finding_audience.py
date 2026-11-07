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


def test_f108_can_be_approved_for_credit_risk():
    body = finding_context("F-108")
    assert body["audience"] == "Credit risk"
    assert body["approval"]["ready"] is True
    assert "A-1002" in body["approval"]["why"] and "A-1005" in body["approval"]["why"]
    assert "Hana Farid" in body["approval"]["why"] and "Yusuf Karim" in body["approval"]["why"]
    assert "The model is Loan model v2" in body["approval"]["why"]
    assert "approve this case" in body["approval"]["why"]
    assert "does not approve the personal loans" in body["approval"]["why"]
    assert "does not promote" in body["approval"]["why"]
    assert "The model is Loan model v2" in body["pipeline"]["summary"]
    assert "Draft the reply" in body["approval"]["how"]
    assert "Nothing is sent" in body["approval"]["how"]
    assert "Loan model v2" in body["approval"]["how"]


def test_f109_can_be_approved_for_lending_ops():
    body = finding_context("F-109")
    assert body["audience"] == "Lending ops"
    assert body["approval"]["ready"] is True
    assert "does not pay a loan" in body["approval"]["why"]
    assert "Nothing is sent" in body["approval"]["how"]


def test_hold_cases_are_not_marked_ready_to_approve():
    assert finding_context("F-101")["approval"] is None


def test_desk_states_the_audience():
    text = (ROOT / "frontend" / "src" / "App.tsx").read_text()
    assert "Reply for" in text
    assert "detail.audience" in text
    assert "detail.pipeline?.summary" in text
