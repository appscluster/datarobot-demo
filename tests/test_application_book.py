"""The personal loan book is a synthetic file of application rows."""
from agent.book import load_book


def test_book_names_the_applicants_and_the_gaps():
    rows = load_book("data/application_book.json")
    ids = {r.application_id for r in rows}
    assert {"A-1001", "A-1002", "A-1003"} <= ids
    west = next(r for r in rows if r.application_id == "A-1001")
    assert west.region == "west" and west.tenant_id == "tenant_demo_acme"
    assert any(r.debt_to_income is None for r in rows)
    assert any(r.income is None and r.loan_amount is None for r in rows)


def test_row_without_a_name_is_still_an_application():
    rows = load_book("data/application_book.json")
    blank = next(r for r in rows if r.applicant_name == "")
    assert blank.application_id
