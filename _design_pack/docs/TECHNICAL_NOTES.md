# Technical notes — AI Eng feasibility sign-off

**Author:** DR-AI-Eng  
**Date:** 2026-11-05 (Asia/Dubai)  
**Status:** Feasible for 15-minute demo + DataRobot packaging path  
**Scope:** Reviews `PLAN.md` stack, GraphRAG v1, and Phase C–F buildability. PM should fold this into `docs/PRD.md` Technical notes.

---

## Verdict

**Go.** The proposed stack is demo-ready within interview timelines if we keep GraphRAG at SQLite + k-hop (≤500 nodes), tools defensive/tenant-scoped only, and HITL as a hard gate (no auto-remediate).

## Stack confirmation

| Layer | Choice | Feasibility | Notes |
|-------|--------|-------------|-------|
| Agent | LangGraph planner→operator→checker + Pydantic | High | Matches code-first brief; POC loop is testable at graph edges |
| API | FastAPI | High | Clean SSE for run traces; DataRobot-friendly |
| UI | React + Vite | High | Separate from agent core; design skills before FE freeze |
| Tools | MCP server | High | Discoverable; easy to refuse destructive verbs in one place |
| GraphRAG | SQLite graph + embeddings | High for v1 | Prefer over Neo4j for portability; hybrid retrieve later |
| OTel | Stub → DataRobot external-agent monitoring | High | Stub sufficient for interview; wire exporter later |
| LLM | Env-configurable (DR gateway / OpenAI / local) | High | No OmniRoute changes on abdul-ai |
| Packaging | Docker Compose + optional `dr` | High | Local-first; align to Agentic Starter where cheap |

## GraphRAG v1 (confirmed)

- **Nodes:** Asset, Finding, CVE/Weakness, Owner, Segment  
- **Edges:** `HAS_FINDING`, `RUNS_ON`, `SAME_SEGMENT`, `OWNED_BY`, `RELATED_CVE`  
- **Retrieve:** entity-link finding → k-hop subgraph → serialize with node ids → LLM cites ids  
- **Cap:** ≤500 nodes; seed from synthetic ThreatAI-shaped fixtures only  
- **Eval:** multi-hop hit-rate on seed questions (e.g. cameras sharing a segment)

Pure vector RAG alone is **not** enough for the “related exposure” story; graph is in scope for v1.

## Tool surface (defensive only)

Implement only:

1. `list_findings` / `get_finding`  
2. `enrich_asset_graph`  
3. `rank_risk`  
4. `draft_remediation` (guidance text; no execution)  
5. `check_scope` (tenant + destructive refusal)  
6. `record_decision` (HITL approve / reject / escalate)

Every tool call requires `tenant_id`. Cross-tenant and destructive requests → refuse + log. No exploit PoCs, payloads, or live customer targeting in-repo.

## Pydantic contracts (minimum)

`Tenant`, `Finding`, `AssetNode`, `RiskScore`, `RemediationDraft`, `Proof`, plus plan/triage result types for planner↔operator↔checker handoff.

## Risks that stay owned in engineering

| Risk | Mitigation |
|------|------------|
| LLM non-determinism | Checker + retries; gold eval set (n≥20); show 2–3 runs in demo |
| GraphRAG overbuild | Hard cap SQLite+k-hop; no Neo4j in v1 |
| Scope creep | Non-goals locked; refuse list reviewed with Nick Fury |
| Secrets / live data | Demo fixtures only; `.env.example`; local commits until Abdul says push |

## Dependencies / blockers for AI Eng

1. PM: `docs/PRD.md` (user, JTBD, non-goals, success metrics) — Eng reviews Technical notes section  
2. Abdul: OK to scaffold after `agent_spec.md` (PLAN §11)  
3. DataRobot CLI auth + LLM selection for `agent_spec.md` model field  
4. Optional: dress rehearsal / swarm before heavy coding  

## Out of scope (reaffirmed)

No offensive tooling, no CBUAE/live tenant binding, no OmniRoute model edits, no auto-ticketing without HITL.

---

*Sign-off: stack and GraphRAG v1 are approved for Phase C design (`agent_spec.md`) and subsequent scaffold when Abdul green-lights.*

## Data layer decision (Abdul — 2026-11-05 Asia/Dubai)

**SQLite + Docker Compose** for v1 (no Postgres). Graph + HITL/audit/llm_calls tables in SQLite; Compose brings up FE+BE+agent locally. Origin repo: https://cursor.com/codebase/dr-abdul-hamid/DataRobot-AI
