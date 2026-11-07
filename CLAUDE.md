# Casework

Interview demo for DataRobot. The product is Casework, a desk for one fictional bank, Emirates NBD Demo. The bank offers personal loans. Loan model v2 scores those applications. Loan model v3 is the challenger and misses 4 more defaults per 100. The analyst decides whether v3 may score live applications. The desk does not approve a person's loan, pay a loan, send a message, or change the live model. All data is synthetic. The signed in tenant is `tenant_demo_acme`. Sign in is `analyst` / `demo`.

## Stack

* Frontend: React 18 and Vite on :43123. Routes are `/`, `/login`, `/brief`, and `/desk` (`frontend/src/Root.tsx`, `App.tsx`, `BriefPage.tsx`). The desk is a bright room. Tokens live in `frontend/src/styles.css`. Keep them.
* Backend: FastAPI on :54123 (`backend/app.py`). The run stream is SSE at `/runs/{id}/events`, with seq replay and a `done` sentinel.
* Agent: LangGraph planner, then operator, then checker (`agent/runner.py`, `agent/checker.py`). They share `TriageState`. The tenant scope guard is `agent/scope.py`.
* Retrieval: SQLite GraphRAG (`agent/graph.py`, `backend/var/graph.db`). Citations are real graph ids.
* Drafts: OmniRoute at `LLM_BASE_URL`, model `gh/gpt-5.6-terra`. LangChain Core builds the prompt in `agent/reply.py`. Token counts from that response are real. Do not label them simulated.
* OpenTelemetry: each run records the span `casework.run`. The span is sent only when `DATAROBOT_API_TOKEN`, `DATAROBOT_ENTITY_ID`, and a DataRobot endpoint are set.
* Docker Compose runs the frontend and the backend. Storage is SQLite. There is no Postgres.

LightRAG and the scanners (Gitleaks, TruffleHog, Trivy, Semgrep, Prowler) are optional code. The running desk does not use them. Do not describe them as part of the demo, and do not turn them on unless Abdul asks.

## Product facts

* The queue is the seeded findings F-101 through F-109. There is no control that creates a new loan request.
* Application rows are `data/application_book.json`. The live scorer is `data/scoring_state.json` (Loan model v2).
* The case map under Connected work and the GraphRAG view are separate. Keep both.
* Approve, Escalate, and Reject happen after the graph finishes. Approve stores a reply. Escalate records the case for the pod lead. Reject returns it to the analyst.
* F-108 approves the case for credit risk on Loan model v2. It does not approve the personal loans, and it does not promote v3.

## Commands

    docker compose up --build                 # FE :43123, BE :54123
    uvicorn backend.app:app --port 54123      # backend, from the repo root
    cd frontend && npm run dev                # frontend
    make eval                                 # 16 evals
    make test-all                             # evals, scanner parser, LightRAG tests, all offline
    cd frontend && npm run build              # must build clean
    python3 tests/sse_contract_regression.py  # needs the backend running
    python3 tests/browser_flow.py             # Playwright, needs frontend and backend running

## Rules

* Plan before editing. For anything bigger than a small fix, write the plan first and confirm it.
* Tests define behaviour. Add or update a test with every change, and run the gates below before saying done.
* Small, reviewable changes. One concern per commit. Do not refactor unrelated code.
* Never guess an API, CLI flag, or schema. Read the code, the docs, or `--help` first.
* Never commit or print secrets. `reports/` is gitignored.
* Keep tenant scoping. Every finding, node, and retrieval is per tenant. A cross tenant request is refused and audited.
* Do not touch OmniRoute. Do not push, merge, or deploy without explicit approval from Abdul.
* Prose written as Abdul has no dashes.
* A UI change is verified in the browser before it is called done.

## Quality gates (all must pass)

`make test-all` (16 evals plus the scanner parser and LightRAG tests), `npm run build`, `tests/sse_contract_regression.py` PASS, `tests/browser_flow.py` with no console errors.

## Skills (project level, in .claude/skills, .cursor/skills, .agents/skills)

* Feature work: `brainstorming`, then `writing-plans`, then `executing-plans` or `subagent-driven-development`.
* Bugs: `systematic-debugging`. Behaviour changes: `test-driven-development`.
* Before saying done: `verification-before-completion`. Reviews: `requesting-code-review`, `receiving-code-review`.
* Any UI change: `ui-ux-pro-max`. Keep the existing tokens.

More: `docs/AGENT_TOOLING.md`, `docs/superpowers/specs/2026-11-07-lending-usecase.md`.
