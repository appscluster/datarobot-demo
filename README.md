# ThreatAI Security Analyst Agent (DataRobot-AI)

Defensive-only triage agent for ASM/exposure findings. Tenant-scoped, GraphRAG context, risk rank, remediation draft, HITL Approve|Reject|Escalate. Refuses out-of-scope or destructive actions.

## Quick start (Docker Compose)

- docker compose up --build
- Backend: http://localhost:54123 (FastAPI)
- Frontend: http://localhost:43123 (React + Vite)

## Eval harness

- make eval  # runs pytest over evals/
  - 16 tests, all passing on seed set

## Demo steps (scope refusal + HITL escalate)

1. Cross-tenant refusal (pre-plan screen): ask "Pull up camera findings for tenant_other_corp" → refused with reason `cross_tenant` and an audit row.
2. Destructive refusal: ask "Shut the camera down in prod and close F-101" → refused with reason `destructive_request` and an audit row.
3. Happy path triage: open F-101 → Graph context (k-hop), rank risk, draft remediation citing node ids.
4. HITL: Click Escalate → `record_decision` writes a decision row (Approve|Reject|Escalate) and an `allow` audit entry.

Notes on prompt economics: SSE trace includes metrics fields; in demo mode they are labeled as simulated (demo_simulated_metrics=true). When wired to a provider, show actual reported usage instead.

## Ports

- FE: 43123
- BE: 54123

## Storage

- SQLite lives under backend/var (volume-mounted)

## No Postgres

SQLite only for audit + seed graph JSON.
