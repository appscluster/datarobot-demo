# Lending pipelines implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the seven static findings into pipelines a visitor can follow from a synthetic application file to a credit risk reply, without ever promoting a model or contacting an applicant.

**Architecture:** Synthetic application rows live in a JSON book. Intake and scoring are pure functions over that book and the existing graph. The desk already drafts through LangGraph and OmniRoute. New work adds the book, the pipeline results on each finding, delivery of the human decision to the right stakeholder queue, and a promotion gate that refuses to change the live scorer.

**Tech Stack:** Python, FastAPI, SQLite, LangGraph, React, the existing OmniRoute draft path.

**Spec:** `docs/superpowers/specs/2026-11-07-lending-usecase.md`

## Global Constraints

- All applicants and the bank are synthetic. Emirates NBD Demo is fictional.
- Every finding, node, and file row is per tenant. `tenant_other_corp` is refused.
- Approve, escalate, and reject record a decision. They do not send email and they do not change which model scores loans.
- The live scorer starts as Loan model v2 and stays Loan model v2.
- The holdout fact stays "4 more defaults per 100". Do not recompute it from the sample file.
- OmniRoute is called only by the existing draft path. Do not edit OmniRoute.
- Metrics from OmniRoute stay real. Do not label them simulated.
- Prose in the product has no dashes.
- Add or update a test with every task. Do not push, merge, or deploy.

## Review Focus

- A file whose tenant is `tenant_other_corp` must not open findings on the Emirates NBD Demo desk. Task 2 tests `test_foreign_file_is_refused`.
- Asking to put v3 live must leave the live scorer as v2. Task 6 tests `test_promotion_does_not_change_the_live_scorer`.
- An empty application file must not invent applicants. Task 2 tests `test_empty_file_has_no_rows`.
- Escalate with no draft still records a pod lead item and does not address an applicant. Task 5 tests `test_escalate_without_draft_goes_to_pod_lead`.
- A row with an id and a blank name is still an application, not a user account. Task 1 tests `test_row_without_a_name_is_still_an_application`.

---

### Task 1: Synthetic application book

**Files:**
- Create: `data/application_book.json`
- Create: `agent/book.py`
- Test: `tests/test_application_book.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Application` with `application_id: str`, `tenant_id: str`, `region: str`, `applicant_name: str`, `income: float | None`, `loan_amount: float | None`, `debt_to_income: float | None`. `load_book(path: str) -> list[Application]`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_application_book.py`
Expected: FAIL, `load_book` is missing.

- [ ] **Step 3: Add the book and `load_book`**

Five rows, all `tenant_demo_acme`. A-1001 is west, named, missing debt to income. A-1002 is named and complete. A-1003 has a blank `applicant_name` and is missing income and loan amount. Two more named rows, one missing debt to income. No holdout count in the file.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_application_book.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/application_book.json agent/book.py tests/test_application_book.py
git commit -m "Add the synthetic personal loan application file."
```

### Task 2: Intake pipeline

**Files:**
- Create: `agent/intake.py`
- Modify: `backend/app.py` findings payload to include `pipeline` when present
- Test: `tests/test_intake.py`

**Interfaces:**
- Consumes: `list[Application]` from `load_book`
- Produces: `inspect_file(rows: list[Application], tenant_id: str) -> IntakeReport`. `IntakeReport.missing_columns: list[str]`, `row_count: int`, `finding_ids: list[str]`. Missing `debt_to_income` adds `F-104`. Missing `income` and `loan_amount` adds `F-102`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_intake.py`
Expected: FAIL, `inspect_file` is missing.

- [ ] **Step 3: Implement `inspect_file`**

Refuse when any row's `tenant_id` is not the session tenant. Do not open findings for an empty file. Sort `finding_ids`.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_intake.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/intake.py tests/test_intake.py backend/app.py
git commit -m "Open intake findings from the application file."
```

### Task 3: Scoring pipeline

**Files:**
- Create: `agent/scoring.py`
- Create: `data/scoring_state.json`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: nothing from intake
- Produces: `ScoringState.live_model: str`, `region_model(region: str) -> str`, `nightly_owner: str | None`, `holdout_note: str`. `load_scoring(path: str) -> ScoringState`.

- [ ] **Step 1: Write the failing test**

```python
def test_v2_scores_the_book_and_the_west():
    state = load_scoring("data/scoring_state.json")
    assert state.live_model == "Loan model v2"
    assert state.region_model("west") == "Loan model v2"
    assert state.nightly_owner is None
    assert state.holdout_note == "4 more defaults per 100"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_scoring.py`
Expected: FAIL, `load_scoring` is missing.

- [ ] **Step 3: Implement the scoring state**

`live_model` is Loan model v2. Region `west` is Loan model v2. `nightly_owner` is null. `holdout_note` is the exact string `4 more defaults per 100`. `challenger_model` is Loan model v3 and is not live.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_scoring.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/scoring.py data/scoring_state.json tests/test_scoring.py
git commit -m "Record which model scores the personal loan book."
```

### Task 4: Show the book and the audience on the desk

**Files:**
- Modify: `backend/app.py` `GET /api/findings/{finding_id}` to add `audience` and `pipeline`
- Modify: `frontend/src/App.tsx` finding stage
- Test: `tests/test_finding_audience.py`

**Interfaces:**
- Consumes: `inspect_file`, `load_scoring`, `load_book`
- Produces: finding JSON `audience: "Credit risk" | "Lending ops"` and `pipeline: {name, summary}`. F-101, F-104, F-105, F-106 audience is Credit risk. F-102, F-103, F-107 audience is Lending ops.

- [ ] **Step 1: Write the failing test**

```python
def test_f101_reply_is_for_credit_risk():
    body = finding_context("F-101")
    assert body["audience"] == "Credit risk"
    assert body["pipeline"]["name"] == "scoring"
    assert "Loan model v2" in body["pipeline"]["summary"]
    assert "A-1001" in body["pipeline"]["summary"]

def test_f102_reply_is_for_lending_ops():
    body = finding_context("F-102")
    assert body["audience"] == "Lending ops"
    assert body["pipeline"]["name"] == "intake"
```

`finding_context` calls the same function the route uses, not a live server.

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_finding_audience.py`
Expected: FAIL

- [ ] **Step 3: Add `finding_context` and render one line on the desk**

Copy: `Reply for {audience}. {pipeline summary}.` Include applicant id A-1001 in the scoring summary. Do not say the reply goes to the applicant.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_finding_audience.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app.py frontend/src/App.tsx tests/test_finding_audience.py
git commit -m "Say who each draft reply is for."
```

### Task 5: Deliver the human decision to the right queue

**Files:**
- Create: `agent/delivery.py`
- Modify: `backend/app.py` `record_decision`
- Modify: `frontend/src/App.tsx` decision status copy
- Test: `tests/test_delivery.py`

**Interfaces:**
- Consumes: decision `approve | escalate | reject`, `audience` from Task 4
- Produces: `deliver(decision: str, audience: str, draft_ready: bool) -> Delivery`. `Delivery.queue: str`, `Delivery.sent: bool` always `False`, `Delivery.note: str`.

- [ ] **Step 1: Write the failing test**

```python
def test_approve_stays_with_credit_risk_and_is_not_sent():
    item = deliver("approve", "Credit risk", True)
    assert item.queue == "Credit risk" and item.sent is False

def test_escalate_without_draft_goes_to_pod_lead():
    item = deliver("escalate", "Credit risk", False)
    assert item.queue == "Pod lead" and item.sent is False
    assert "applicant" not in item.note.lower()

def test_reject_returns_to_the_analyst():
    item = deliver("reject", "Lending ops", True)
    assert item.queue == "Analyst"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_delivery.py`
Expected: FAIL

- [ ] **Step 3: Implement `deliver` and show `item.note` in `#decision-status`**

Approve note: `Recorded for Credit risk. Nothing was sent.` Escalate note: `Escalated to the pod lead. Nothing was sent.` Reject note: `Returned to the analyst for rework.`

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_delivery.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/delivery.py backend/app.py frontend/src/App.tsx tests/test_delivery.py
git commit -m "Route each decision to the stakeholder who owns it."
```

### Task 6: Promotion gate

**Files:**
- Create: `agent/promotion.py`
- Modify: `agent/scope.py` only if a new phrase must match the existing destructive matcher. Prefer calling `guard` with the existing shut down and promote text before adding a pattern.
- Test: `tests/test_promotion.py`

**Interfaces:**
- Consumes: `ScoringState` from `load_scoring`
- Produces: `request_promotion(state: ScoringState, actor: str) -> tuple[ScoringState, str]`. The returned state has the same `live_model`. The string reason is `promotion_refused`.

- [ ] **Step 1: Write the failing test**

```python
def test_promotion_does_not_change_the_live_scorer():
    before = load_scoring("data/scoring_state.json")
    after, reason = request_promotion(before, "analyst:demo-1")
    assert after.live_model == "Loan model v2"
    assert reason == "promotion_refused"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_promotion.py`
Expected: FAIL

- [ ] **Step 3: Implement `request_promotion`**

Return a copy of the state. Do not write a new live model. Wire the existing "Shut the model down in prod" control to this same refusal reason in the API response, without changing the live scorer file.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_promotion.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/promotion.py backend/app.py tests/test_promotion.py
git commit -m "Refuse promotion without changing the live model."
```

### Task 7: Lending ops review and retrain

**Files:**
- Create: `agent/ops.py`
- Test: `tests/test_ops.py`

**Interfaces:**
- Consumes: nothing from promotion
- Produces: `weekly_review() -> dict` with `owner: None` and `status: "open"`. `retrain_note() -> dict` with `status: "open"` and `started: False`. `request_rescore() -> str` returns `rescore_refused`.

- [ ] **Step 1: Write the failing test**

```python
def test_weekly_review_has_no_owner_and_retrain_has_not_started():
    assert weekly_review()["owner"] is None
    note = retrain_note()
    assert note["status"] == "open" and note["started"] is False

def test_rescore_is_refused():
    assert request_rescore() == "rescore_refused"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_ops.py`
Expected: FAIL

- [ ] **Step 3: Implement the three functions**

No function writes an owner or starts a retrain. F-103 and F-107 keep using these results in `finding_context`.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_ops.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/ops.py backend/app.py tests/test_ops.py
git commit -m "Keep lending ops work open until a person acts."
```

### Task 8: Explain the path on the brief page

**Files:**
- Modify: `frontend/src/BriefPage.tsx`
- Test: `tests/test_pages_contract.py`

**Interfaces:**
- Consumes: the audience and pipeline names from Tasks 4 to 7
- Produces: a section `The path` with the eight pipeline names in order: Intake, Scoring, Evidence, Casework, Decision, Promotion, Lending ops, Tenant wall.

- [ ] **Step 1: Extend the failing assertion**

```python
def test_brief_explains_the_lending_path():
    text = (SRC / "BriefPage.tsx").read_text()
    for name in ("Intake", "Scoring", "Evidence", "Casework", "Decision", "Promotion", "Lending ops", "Tenant wall"):
        assert name in text
    assert "applicant" in text.lower()
    assert "Credit risk" in text
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest -q tests/test_pages_contract.py::test_brief_explains_the_lending_path`
Expected: FAIL

- [ ] **Step 3: Add the section**

One short paragraph per pipeline, under the existing "Who this serves" section. Do not remove that section. Say applicants exist only as rows in the file. Say the reply is for credit risk or lending ops. Say promotion does not change v2.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/bin/python -m pytest -q tests/test_pages_contract.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/BriefPage.tsx tests/test_pages_contract.py
git commit -m "Explain the lending path and who each reply is for."
```
