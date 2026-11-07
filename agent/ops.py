"""Lending ops work that a person still has to do. Nothing starts by itself."""


def weekly_review() -> dict:
    return {"owner": None, "status": "open"}


def retrain_note() -> dict:
    return {"status": "open", "started": False}


def request_rescore() -> str:
    return "rescore_refused"
