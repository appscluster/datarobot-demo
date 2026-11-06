# DataRobot-Demo: ThreatAI Security Analyst Agent

Defensive triage agent demo for a DataRobot interview. All data is synthetic.

## Stack

* Backend: FastAPI on :54123 (`backend/app.py`), SSE run stream at `/runs/{id}/events` with seq replay and a `done` sentinel.
* Agent: LangGraph planner, operator, checker (`agent/runner.py`, `agent/checker.py`), tenant scope guard (`agent/scope.py`).
* Retrieval: SQLite GraphRAG (`agent/graph.py`, `backend/var/graph.db`). Optional LightRAG behind `RETRIEVAL_BACKEND=lightrag` (`docs/LIGHTRAG.md`), default off.
* Scanner findings: `agent/security_sources.py` (Gitleaks, TruffleHog, Trivy, Semgrep, Prowler) into SQLite `backend/var/security.db`.
* Frontend: React 18 + Vite on :43123 (`frontend/src/App.tsx`, tokens in `styles.css`). Dark SOC console redesign; keep it.
* Docker Compose (SQLite only, no Postgres). Profiles: `security`, `lightrag`.

## Commands

    docker compose up --build                 # FE :43123, BE :54123
    uvicorn backend.app:app --port 54123      # backend (from repo root)
    cd frontend && npm run dev                # frontend
    make eval                                 # 16 evals
    make test-all                             # evals + scanner parser + LightRAG tests (offline)
    cd frontend && npm run build              # must build clean
    python3 tests/sse_contract_regression.py  # needs backend running
    python3 tests/browser_flow.py             # Playwright, needs FE and BE running
    make security-scan | scan-secrets | scan-deps | scan-sast   # this repo only
    make scan-cloud                           # Prowler: PROWLER_OPT_IN=1 + your own creds only
    make security-ingest                      # reports/security (or fixtures) into the agent
    make lightrag-smoke                       # real lightrag-hku, fake LLM, offline

## Rules

* Plan before editing. For anything bigger than a small fix, write the plan first and confirm it.
* Tests define behaviour. Add or update a test with every change; run the gates below before saying done.
* Small, reviewable changes. One concern per commit. Do not refactor unrelated code.
* Never guess an API, CLI flag or schema. Read the code, the docs or `--help` first.
* Never commit or print secrets. Scanner findings store rule, file, line, fingerprint and a masked preview only. `reports/` is gitignored.
* Defensive only. Scan this repo, images built from it and the owner's own cloud account; nothing external. TruffleHog verification stays off unless the owner opts in.
* Keep tenant scoping: every finding, node and retrieval is per tenant; cross tenant requests are refused and audited.
* Metrics in the demo are simulated and must stay labelled as simulated.
* Do not touch OmniRoute. Do not push, merge or deploy without explicit approval from Abdul.
* Prose written as Abdul has no dashes.

## Quality gates (all must pass)

`make test-all` (16 evals + parser + LightRAG tests), `npm run build`, `tests/sse_contract_regression.py` PASS, `tests/browser_flow.py` with no console errors.

## Skills (project level, in .claude/skills, .cursor/skills, .agents/skills)

* Feature work: `brainstorming`, then `writing-plans`, then `executing-plans` or `subagent-driven-development` (Superpowers).
* Bugs: `systematic-debugging`. Behaviour changes: `test-driven-development`.
* Before saying done: `verification-before-completion`. Reviews: `requesting-code-review`, `receiving-code-review`.
* Any UI change: `ui-ux-pro-max`, plus Taste and Impeccable where installed; keep the existing tokens.
* Spec driven phases: GSD Core `/gsd-*` commands once installed (`scripts/install_agent_tooling.sh`).

More: `docs/AGENT_TOOLING.md`, `docs/ARCHITECTURE.md`, `security/README.md`, `docs/LIGHTRAG.md`.
