# PRD — ThreatAI Security Analyst Agent (v1)

**Product:** ThreatAI Security Analyst Agent  
**Phase:** A (PM)  
**Owners:** PM (Maria Hill / DR-PM); AI Eng review: Rhodey / DR-AI-Eng  
**Status:** AI Eng signed off (APPROVED 2026-11-05)  
**Data:** Synthetic demo only

---

## Problem

Security teams drown in ASM and exposure findings (open cameras, PeopleSoft login surfaces, username OSINT) with no trusted triage loop. Analysts lack graph context across related assets and cannot safely give an agent broad agency. Manual triage is slow, inconsistent, and hard to audit for regulated buyers.

## Users and buyer

| Role | Who | Need |
|------|-----|------|
| Primary user | Security analyst / ASM operator (demo persona) | Triage a finding with related-asset context and a draft remediation they can trust |
| Secondary user | Security lead | Review HITL decisions, audit trail, escalations |
| Buyer | DataRobot Professional Services customer in a regulated industry | Governed agentic triage that fits PS deployment, monitoring, and audit expectations |

## Jobs to be done

1. When a new finding lands in my tenant queue, I want graph-backed context and a risk rank so I know what to work next.
2. When I open a finding, I want a non-destructive remediation draft with citations to graph nodes so I can act or escalate with evidence.
3. When an agent proposes an action, I want approve / reject / escalate with a logged decision so production never changes without a human.
4. When a request is out of tenant or destructive, I want a hard refusal and audit entry so scope stays enforceable.

## Scope for v1 (agent behavior)

1. Ingest or select a finding in tenant scope.
2. Retrieve GraphRAG neighborhood (related hosts, services, prior findings, owners).
3. Rank risk with explicit factors.
4. Draft remediation steps (non-destructive guidance only).
5. Checker verifies citations, scope, and absence of destructive verbs.
6. Human approves, rejects, or escalates — agent never “fixes” production itself.

App shell: React UI + FastAPI + LangGraph agent + MCP tools + SQLite graph/vectors; primary start `docker compose up` (optional `dr run dev`); OTel stub for DataRobot external-agent monitoring.

## Non-goals (locked)

- No offensive exploit PoCs, payloads, or unauthorized scanning.
- No live CBUAE / customer production targeting in this repo.
- No OmniRoute model changes on abdul-ai.
- No auto-publish of remediations to ticketing without HITL.
- **Not production-ready software (PDF / B15):** interviewers expect a working demo prototype with a clear productization path — not a hardened production system. Do not claim prod readiness in the deck or README.

## Success metrics (tied to E1–E6)

| Eval | Pass bar (from PLAN §5) |
|------|-------------------------|
| E1 Functional demo | Cold start ≤ 60 s; E2E triage ≤ 45 s; cross-tenant refusal 100%; destructive request always refused + logged |
| E2 Agent quality (n≥20) | Risk rank within ±1 band ≥ 80%; cites ≥1 node id ≥ 90%; hallucinated asset id ≤ 5%; checker catch missing citation ≥ 95% |
| E3 GraphRAG | Multi-hop seed accuracy ≥ 75%; retrieve p50 ≤ 500 ms local |
| E4 Engineering hygiene | Backend tests green; FE production build clean; no secrets in git; defensive-only tool checklist signed |
| E5 Presentation / PS fit | Talk 13–15 min; live demo 2/2 dry runs; productize story names DR monitoring + template reuse; cost/quality + model-strategy beats present |
| E6 AI Eng competencies | Stable prompt prefix documented; cache/token fields on run log (or `provider_N/A`); **cache hit ratio tracked (target ≥ 60% on 2nd+ finding when provider reports cache)**; **cost/tokens per triage reported**; **eval gate in CI** (prompt/agent changes must pass E2/E3); ≥4 defended architecture decisions; fine-tune trigger written (no fine-tune in v1 demo) |

Targets above labeled **target** are design goals — do not invent measured production numbers in the deck.

## Acceptance criteria (checklist)

- [ ] Happy path: select one seeded finding → agent completes planner/operator/checker → risk rank + remediation draft shown.
- [ ] Cross-tenant request is refused 100% of test cases and written to the audit log.
- [ ] Destructive request (e.g. “shut it down in prod” / “go fix it”) is refused and logged; no tool mutates production.
- [ ] Remediation draft cites ≥1 graph node id visible in the UI.
- [ ] HITL: human can Approve, Reject, or Escalate; decision is persisted.
- [ ] Audit log records triage run id, tenant id, finding id, decision, and refusal reason when applicable.
- [ ] OpenTelemetry stub emits a trace/span for an agent run (export target configurable / no-op OK).
- [ ] One-command start: primary `docker compose up` (optional `dr run dev`) brings up FE + BE + agent; chat/queue UI loads.
- [ ] Prompt prefix ordered for cache (system + tool schemas + tenant graph context; finding last); run log exposes token/cache fields or `provider_N/A`.
- [ ] Cache hit ratio and tokens/cost per triage are tracked (targets documented; no invented measurements).
- [ ] Eval gate: seed gold set; prompt/agent changes must pass E2/E3 in CI or `make eval` before merge.
- [ ] README/deck state this is a demo prototype with a productization path — not production-ready (B15).

## Technical notes (AI Eng sign-off)

Proposed stack (PLAN §6) — for Rhodey / DR-AI-Eng review:

| Layer | Choice |
|-------|--------|
| Agent | LangGraph + Pydantic |
| API | FastAPI |
| UI | React + Vite |
| Tools | MCP server (tenant-scoped, defensive) |
| GraphRAG | SQLite graph + embeddings (≤500 nodes) |
| Observability | OpenTelemetry → DataRobot external agent monitoring (stub OK) |
| LLM | Configurable via env (OpenAI / DR gateway / local); no OmniRoute edits |
| Packaging | Docker Compose + optional `dr` scripts |

**AI Eng sign-off:** DR-AI-Eng — APPROVED 2026-11-05 (Asia/Dubai). Feasibility + stack confirmed; GraphRAG SQLite+k-hop ≤500 nodes OK for demo. See docs/TECHNICAL_NOTES.md, agent_spec.md, docs/GRAPHRAG_ONTOLOGY.md, docs/SCOPE_GUARD.md, docs/EVAL_HARNESS.md.

Additional AI Eng design docs: `docs/ARCHITECTURE.md` (defended decisions, demo scope B13/B15), `docs/PROMPT_CACHE.md` (C1 token/cache meters), `docs/MODEL_STRATEGY.md` (C3, no fine-tune in v1), `evals/` (C2 harness sketch). LLM model in `agent_spec.md` is a placeholder until `dr auth login` + `list_llm_models.py`.

## Resolved decisions (AI Eng 2026-11-05)

| # | Topic | Decision |
|---|-------|----------|
| 1 | Entrypoint | Primary: `docker compose up`. Optional: `dr run dev` (DataRobot Agentic Starter alignment). E1 cold-start timing uses compose. |
| 2 | Demo LLM | Env gateway for live runs + recorded/cached replay (prompt-hash keyed, UI label "recorded") for offline/CI. No local model required for v1. |
| 3 | Tenants / findings | `tenant_demo_acme` (F-101..F-107 demo queue; F-108..F-120 eval-only). Foreign refusal only: `tenant_other_corp` (`finding:F-901`, `asset:oc-cam-91`). |
| 4 | Docs timing | `ARCHITECTURE.md` / `MODEL_STRATEGY.md` before scaffold; `PRODUCTIZE.md` PM-owned before Phase G deck. |
| 5 | HITL persistence | SQLite `decisions` (source of truth) + `audit_log` allow row + OTel event `hitl.decision` (exporter may be no-op in v1). |

## Open questions (remaining)

_None blocking Phase B/C. Park non-blocking items in backlog._
