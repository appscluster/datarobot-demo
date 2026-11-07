"""Who a draft is for, and which pipeline produced the case."""
from pathlib import Path

from agent.book import load_book
from agent.intake import inspect_file
from agent.ops import retrain_note, weekly_review
from agent.scoring import load_scoring

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "data" / "application_book.json"
SCORING = ROOT / "data" / "scoring_state.json"
TENANT = "tenant_demo_acme"

AUDIENCE = {
    "F-101": "Credit risk",
    "F-104": "Credit risk",
    "F-105": "Credit risk",
    "F-106": "Credit risk",
    "F-102": "Lending ops",
    "F-103": "Lending ops",
    "F-107": "Lending ops",
}


def finding_context(finding_id: str) -> dict:
    rows = load_book(str(BOOK))
    report = inspect_file(rows, TENANT)
    state = load_scoring(str(SCORING))
    west = next(row for row in rows if row.region == "west")
    audience = AUDIENCE.get(finding_id, "Credit risk")
    if finding_id == "F-102":
        missing = ", ".join(name.replace("_", " ") for name in report.missing_columns if name != "debt_to_income")
        pipeline = {"name": "intake", "summary": f"The file is missing {missing}."}
    elif finding_id == "F-104":
        pipeline = {
            "name": "evidence",
            "summary": f"Debt to income left the file. {state.challenger_model} still expects it.",
        }
    elif finding_id == "F-103":
        review = weekly_review()
        owner = review["owner"] or "no owner"
        pipeline = {"name": "lending ops", "summary": f"The weekly credit review is {review['status']} and has {owner}."}
    elif finding_id == "F-107":
        note = retrain_note()
        started = "started" if note["started"] else "not started"
        pipeline = {"name": "lending ops", "summary": f"The retrain note is {note['status']} and has {started}."}
    elif finding_id == "F-106":
        owner = state.nightly_owner or "no owner"
        pipeline = {
            "name": "scoring",
            "summary": (
                f"Nightly scoring has {owner}. {state.live_model} scores the book, "
                f"including {west.application_id}."
            ),
        }
    else:
        pipeline = {
            "name": "scoring",
            "summary": (
                f"{state.live_model} scores the book, including {west.application_id}. "
                f"The holdout note is {state.holdout_note}."
            ),
        }
    return {"finding_id": finding_id, "audience": audience, "pipeline": pipeline}
