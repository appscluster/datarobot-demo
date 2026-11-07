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
    "F-108": "Credit risk",
    "F-109": "Lending ops",
}


def _complete(rows) -> list:
    return [
        row for row in rows
        if row.applicant_name and row.income is not None and row.loan_amount is not None and row.debt_to_income is not None
    ]


def _complete_ids(rows) -> list[str]:
    return [row.application_id for row in _complete(rows)]


def _complete_people(rows) -> str:
    parts = [f"{row.applicant_name} {row.application_id}" for row in _complete(rows)]
    return " and ".join(parts) if parts else "no application"


def finding_context(finding_id: str) -> dict:
    rows = load_book(str(BOOK))
    report = inspect_file(rows, TENANT)
    state = load_scoring(str(SCORING))
    west = next(row for row in rows if row.region == "west")
    audience = AUDIENCE.get(finding_id, "Credit risk")
    complete = _complete_ids(rows)
    named = " and ".join(complete) if complete else "no application"
    people = _complete_people(rows)
    if finding_id == "F-102":
        missing = " and ".join(name.replace("_", " ") for name in report.missing_columns if name != "debt_to_income")
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
    elif finding_id == "F-108":
        pipeline = {
            "name": "scoring",
            "summary": (
                f"This case is approved for credit risk. The model is {state.live_model}. "
                f"{people} stay on {state.live_model} because each application has income, a loan amount, "
                f"and debt to income, and {state.live_model} already scored them. "
                f"{state.challenger_model} is not the model. "
                f"Approving records that decision. It does not approve a personal loan and it does not promote {state.challenger_model}."
            ),
        }
    elif finding_id == "F-109":
        pipeline = {
            "name": "intake",
            "summary": (
                f"{named} have a name, income, a loan amount, and debt to income. "
                f"The next scheduled batch can include them."
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
    approval = None
    if finding_id == "F-108":
        approval = {
            "ready": True,
            "why": (
                f"Credit risk can approve this case. The model is {state.live_model}. "
                f"{people} have income, a loan amount, and debt to income, so {state.live_model} already scored them. "
                f"The reply names {state.live_model} and says why the case is approved. "
                f"It does not promote {state.challenger_model} and it does not approve the personal loans."
            ),
            "how": (
                f"Draft the reply. When the checker passes, Approve records it for {audience}. "
                f"Nothing is sent. The model is {state.live_model}, and the live model stays {state.live_model}."
            ),
        }
    elif finding_id == "F-109":
        approval = {
            "ready": True,
            "why": (
                f"{named} have a name, income, a loan amount, and debt to income. "
                f"The broken file stays out. Approving records these rows for the next scheduled batch. "
                f"It does not rescore last night and it does not pay a loan."
            ),
            "how": (
                f"Draft the reply. When the checker passes, Approve records it for {audience}. "
                f"Nothing is sent."
            ),
        }
    return {"finding_id": finding_id, "audience": audience, "pipeline": pipeline, "approval": approval}
