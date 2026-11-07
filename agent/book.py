"""Synthetic personal loan applications. Rows are not user accounts."""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Application:
    application_id: str
    tenant_id: str
    region: str
    applicant_name: str
    income: float | None
    loan_amount: float | None
    debt_to_income: float | None


def load_book(path: str) -> list[Application]:
    raw = json.loads(Path(path).read_text())
    return [Application(**row) for row in raw]
