"""Lending ops work stays open until a person acts."""
from agent.cases import finding_context
from agent.ops import retrain_note, request_rescore, weekly_review


def test_weekly_review_has_no_owner_and_retrain_has_not_started():
    assert weekly_review()["owner"] is None
    note = retrain_note()
    assert note["status"] == "open" and note["started"] is False


def test_rescore_is_refused():
    assert request_rescore() == "rescore_refused"


def test_open_ops_work_is_on_the_findings():
    review = finding_context("F-103")["pipeline"]["summary"].lower()
    retrain = finding_context("F-107")["pipeline"]["summary"].lower()
    assert "no owner" in review
    assert "not started" in retrain
    assert "rescore_refused" not in review
