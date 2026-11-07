"""Intake opens findings from missing columns and refuses another tenant."""
import pytest

from agent.book import Application, load_book
from agent.intake import inspect_file


def test_missing_columns_open_the_intake_findings():
    report = inspect_file(load_book("data/application_book.json"), "tenant_demo_acme")
    assert report.row_count == 5
    assert "debt_to_income" in report.missing_columns
    assert "income" in report.missing_columns and "loan_amount" in report.missing_columns
    assert report.finding_ids == ["F-102", "F-104"]


def test_empty_file_has_no_rows():
    report = inspect_file([], "tenant_demo_acme")
    assert report.row_count == 0 and report.finding_ids == []


def test_foreign_file_is_refused():
    foreign = [Application("A-9", "tenant_other_corp", "west", "Other", 1, 1, 1)]
    with pytest.raises(PermissionError):
        inspect_file(foreign, "tenant_demo_acme")
