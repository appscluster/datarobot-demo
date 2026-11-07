"""Read an application file and open the intake findings it supports."""
from dataclasses import dataclass

from agent.book import Application


@dataclass
class IntakeReport:
    missing_columns: list[str]
    row_count: int
    finding_ids: list[str]


def inspect_file(rows: list[Application], tenant_id: str) -> IntakeReport:
    if any(row.tenant_id != tenant_id for row in rows):
        raise PermissionError("application file is outside this tenant")
    if not rows:
        return IntakeReport(missing_columns=[], row_count=0, finding_ids=[])
    missing = [
        name
        for name in ("debt_to_income", "income", "loan_amount")
        if any(getattr(row, name) is None for row in rows)
    ]
    finding_ids = []
    if "income" in missing and "loan_amount" in missing:
        finding_ids.append("F-102")
    if "debt_to_income" in missing:
        finding_ids.append("F-104")
    finding_ids.sort()
    return IntakeReport(missing_columns=missing, row_count=len(rows), finding_ids=finding_ids)
