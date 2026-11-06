# DataRobot-AI — ThreatAI Security Analyst Agent

**Project path:** `~/projects/DataRobot-AI`  
**Assignment:** DataRobot Professional Services — Build an AI Agent  
**Selected idea:** #1 ThreatAI Security Analyst Agent  
**Created:** 2026-11-05 (Asia/Dubai)  
**Owners:** Product Manager (Maria Hill / DR-PM) + AI Engineer (Rhodey / DR-AI-Eng), coordinated by Tony Stark · VP

---

## 0. Mission (one sentence)

Ship a working, code-first security triage agent (React frontend + FastAPI/LangGraph backend) that ingests tenant-scoped ThreatAI-style findings, uses GraphRAG for related-asset context, ranks risk, drafts remediations with human-in-the-loop gates, refuses out-of-scope or destructive actions, and is demoable in 15 minutes with a clear path to productize on DataRobot for regulated customers.

---

## 1. PDF / brief requirements map

> Source: original PDF now saved as `assignment-brief.pdf` (re-attached 2026-11-05). Verbatim requirements below.

| # | Brief requirement | How this project addresses it | Eval criterion (pass bar) | Status |
|---|-------------------|-------------------------------|---------------------------|--------|
| B1 | Functioning agent as a **full app** (frontend + backend) | React (Vite) UI + FastAPI API + LangGraph agent + MCP tool server, runnable with one command | `dr run dev` / `docker compose up` starts FE+BE+agent; chat + queue UI load; one end-to-end triage completes | [~] |
| B2 | **Code-first** approach (LangChain / LangGraph / CrewAI / Pydantic / LlamaIndex) | LangGraph planner→operator→checker; Pydantic contracts for Finding, Plan, TriageResult, Proof; typed tools | Agent graph is Python code (not no-code); schemas validate; unit tests cover graph edges | [x] |
| B3 | **15-minute presentation** covers problem, solution, architecture | Deck outline in `docs/PRESENTATION.md` timed to 15 min | Dry-run fits ≤15 min; each section has a spoken script + 1 slide | [ ] |
| B4 | Live **demo** in the presentation | Seeded demo tenant + 5–8 sample findings (camera, PeopleSoft surface, OSINT username) | Demo script runs without live internet except LLM; happy path + refusal path shown | [ ] |
| B5 | Call out **challenges** honestly | `docs/CHALLENGES.md` (non-determinism, scope, GraphRAG freshness, HITL latency) | At least 3 challenges with mitigation chosen | [ ] |
| B6 | **Vision for DataRobot customers** + how to productize | `docs/PRODUCTIZE.md`: agent template + OTel → DataRobot monitoring + PS playbook | Narrative names PS buyer, governance, template reuse | [ ] |
| B7 | Submit **GitHub code** + **deck** by email | Repo README + `docs/deck/` (or PPTX); submission email draft ready | Public or private GitHub repo link + deck file exist | [ ] |
| B8 | Maps to **DataRobot PS / customer value** | Regulated ASM triage, governance, HITL, audit trail | Story fits AI Engineer–PS role (agentic + GenAI + deploy) | [ ] |
| B9 | Prefer DataRobot **agent skills / platform path** | Use `datarobot-agent-assist` for `agent_spec.md`; LLM selection skill; external-agent OTel | `agent_spec.md` present; OTel hooks stubbed; LLM path documented | [ ] |
| B10 | **Challenges & Learnings** (PDF asks both) | `docs/CHALLENGES.md` includes obstacles *and* what we learned | ≥3 challenges each with a learning | [ ] |
| B11 | **Problem-Solving Acumen** (what they look for) | Clear ASM triage inefficiency; passionate ThreatAI story | PRD problem statement ≤½ page, crisp | [ ] |
| B12 | **Strategic Vision** | Connect agent → regulated customer outcomes → PS template | PRODUCTIZE.md + Vision slide | [ ] |
| B13 | **Technical Credibility** | Working demo + defended stack choices | Live demo + ARCHITECTURE.md | [ ] |
| B14 | **Creativity & Passion** | GraphRAG + HITL refusals + cache/token economics as distinctive angles | Demo shows refusal + graph neighborhood + cost line | [ ] |
| B15 | **Not production-ready** (PDF expectation) | Vertical slice, seed data, mocked LLM fallback OK | README states demo scope; no fake “prod hardened” claims | [ ] |



---

## 1a. Assignment PDF (verbatim summary)

**Title:** Interview Assignment: Build an AI Agent (DataRobot Professional Services / agentic strategy)

**Task:** Build a functioning AI agent + short presentation for the next interview. Problem of your choice (personal productivity → complex business automation). **IMPORTANT:** final output is a **complete application (frontend + backend)**.

**Mission:**
1. Identify a real-world problem/inefficiency an agent can address
2. Build with open-source frameworks (LangChain, LangGraph, CrewAI, Pydantic, or LlamaIndex) using a **code-first** approach
3. 15-minute presentation + live demo covering: Problem; Solution (architecture, tools, why); Live Demo; Challenges & Learnings; Vision (DataRobot customer problem + how to scale/productize)

**What they’re looking for (not just coding):** Problem-Solving Acumen; Strategic Vision; Technical Credibility; Creativity & Passion. They are **not** expecting a production-ready app — how you think and build.

**Submission:** Code (GitHub preferred) + presentation deck **via email**; team reviews then follows up.

---

## 1b. AI Engineer role competencies (interview prep → product)

Source: vibe-coding vs AI-engineering checklist (four skills a strong AI engineer demonstrates). Useful for the DataRobot PS **AI Engineer** role narrative and as build requirements for this agent — not a repo to install.

| # | Competency | Why DataRobot PS cares | How ThreatAI Security Analyst Agent shows it | Status |
|---|------------|------------------------|----------------------------------------------|--------|
| C1 | **Structure context for prompt caching** — stable prefixes so providers reuse KV cache; track cache hits and token cost per run | PS customers care about cost at scale; “we don’t reprocess the same system prompt every hop” is a real deliverable | Stable system + tool schema prefix; tenant/policy block ordered for cache; run log fields: `prompt_tokens`, `cached_tokens`, `cache_hit_ratio`, `usd_estimate`; UI/trace shows cost per triage | [~] design in `docs/PROMPT_CACHE.md` + agent_spec; code pending |
| C2 | **Build evals** — for agent output *and* for prompts/code | Release gates, regression, customer trust | Golden set of findings with gold risk band + citation expectations (E2); prompt/unit tests for scope refusal; checker as online eval; `evals/` harness + CI job | [x] eval harness in repo; 16 tests green |
| C3 | **Know when to fine-tune a small model** | Long-running agent loops; latency/cost vs frontier models | Document decision in `docs/MODEL_STRATEGY.md`: start with gateway LLM; candidate fine-tune = risk-ranker or citation checker on Qwen local if eval plateau; **do not fine-tune in v1 demo** | [x] `docs/MODEL_STRATEGY.md` (decision doc; no fine-tune v1) |
| C4 | **Draw the architecture and defend every decision** | Client workshops; C-level storytelling | `docs/ARCHITECTURE.md` + mermaid in PRESENTATION; one slide “why LangGraph / why GraphRAG / why HITL / why SQLite graph” | [~] `docs/ARCHITECTURE.md` written; slide pending |

### What you already cover vs the gap

- **Evals:** LogixFlow golden-question style → port as finding gold labels; ThreatAI red-team mindset → scope/refusal release gate.
- **Small models:** Local Qwen on abdul-ai is the fine-tune *option* story, not a build for the interview unless time allows.
- **Architecture:** Hermes Planner → Operator → Checker is the loop we ship in LangGraph.
- **Real gap — caching & token economics:** nothing in our stack yet tracks cache hits or $ per run. **Add for this project** (quick, high interview value):
  - [ ] Structured prompts with a frozen prefix (system + tool defs + tenant policy) and a variable suffix (finding + graph neighborhood)
  - [~] Per-run metrics in agent trace + OpenTelemetry attributes
  - [ ] One slide / spoken line: “here’s cache hit ratio on the second finding in the same session”
  - [ ] Optional later: same meters on Hermes loop / OmniRoute (out of scope for DataRobot-AI unless you ask)

### Presentation mapping (use in the 15-minute talk)

1. Context caching → Challenges or Architecture (“cost control”)
2. Evals → Demo closer + Challenges (“how we know it works”)
3. Fine-tune decision → Productize / Model strategy (30 seconds)
4. Architecture defense → Architecture section (already planned)


---

## 2. Master checklist (build order)

### Phase A — Plan & product (PM owns; AI Eng reviews)

- [x] Create `~/projects/DataRobot-AI` folder
- [x] Write this `PLAN.md` with brief map + eval criteria
- [x] PM: one-page PRD (`docs/PRD.md`) — user, JTBD, non-goals, success metrics
- [x] PM: demo script (`docs/DEMO_SCRIPT.md`) timed to 5 minutes inside the 15-minute talk
- [x] PM: presentation outline (`docs/PRESENTATION.md`) — problem → solution → architecture → demo → challenges → productize
- [x] AI Eng: sign off on feasibility and stack choices in PRD “Technical notes” (2026-11-05)
- [x] Confirm GraphRAG approach (see §4) and seed ontology (`docs/GRAPHRAG_ONTOLOGY.md`)

### Phase B — Design system (Impeccable + UI UX Pro Max + Taste + anti-AI-UI-tells)

- [ ] Install / load skills in project: `impeccable`, `ui-ux-pro-max`, `design-taste-frontend`, `anti-ai-ui-tells`
- [ ] Design brief: security ops console, calm density, no purple gradients / emoji headings / generic shadcn clone
- [ ] Wireframes: Queue, Finding detail, Agent trace, Graph context, HITL approve/refuse
- [ ] Design tokens + component inventory (`docs/DESIGN.md`)
- [ ] Taste / Impeccable critique pass before FE freeze

### Phase C — Agent design (DataRobot agent-assist)

- [ ] Author `agent_spec.md` via datarobot-agent-assist (Design path)
- [ ] Define tools (tenant-scoped only; defensive; no exploit payloads):
  - `list_findings` / `get_finding`
  - `enrich_asset_graph` (GraphRAG)
  - `rank_risk`
  - `draft_remediation`
  - `check_scope` (refuse out-of-tenant / destructive)
  - `record_decision` (HITL approve / reject / escalate)
- [ ] Planner → Operator → Checker loop (Hermes POC pattern)
- [ ] Pydantic models: `Tenant`, `Finding`, `AssetNode`, `RiskScore`, `RemediationDraft`, `Proof`
- [ ] Optional dress-rehearsal / swarm simulate before heavy coding

### Phase D — Backend + GraphRAG

- [x] Scaffold FastAPI app (`backend/`)
- [x] LangGraph agent package (`agent/`)
- [ ] MCP server hosting tools (`mcp_server/`)
- [ ] GraphRAG store: knowledge graph of assets↔findings↔CVEs↔owners (NetworkX / Neo4j Lite / SQLite+edges; vector index for chunk retrieval)
- [ ] Seed graph from synthetic ThreatAI findings (cameras, PeopleSoft surface, Sherlock usernames) — **demo data only**
- [x] Scope guard middleware: every tool call must carry `tenant_id`; refuse cross-tenant
- [x] OpenTelemetry instrumentation stub for DataRobot external-agent monitoring
- [~] **Prompt-cache / token economics:** frozen prompt prefix; log `prompt_tokens`, `cached_tokens`, `cache_hit_ratio`, cost estimate per run (competency C1)
- [x] **Evals harness** under `evals/`: gold findings, scope refusal cases, citation checks; wire to CI (competency C2)
- [ ] Unit + integration tests for graph edges, scope refusal, ranking

### Phase E — Frontend

- [x] Scaffold React + Vite (`frontend/`) per design tokens
- [x] Screens: Login/tenant (demo), Findings queue, Detail + evidence, Agent run trace, Graph panel, HITL actions
- [x] Streaming / polling for agent steps (prefer SSE)
- [x] Empty / loading / error states; keyboard-friendly triage
- [ ] Impeccable + Taste polish pass; anti-AI-UI audit

### Phase F — DataRobot packaging & ops

- [ ] Align layout with DataRobot Agentic Starter conventions where practical (`dr` / `task` scripts)
- [x] `docker-compose.yml` for local FE+BE+agent+MCP (+ graph store)
- [ ] README: setup, demo, architecture diagram
- [ ] `docs/PRODUCTIZE.md` + CI sketch (`datarobot-app-framework-cicd`)
- [ ] Eval harness (§5) green on seed set

### Phase G — Presentation & submission

- [ ] `docs/ARCHITECTURE.md` with defended decisions (competency C4)
- [ ] `docs/MODEL_STRATEGY.md` fine-tune vs gateway decision (competency C3)
- [ ] Talk slide/line on cache hit ratio + eval gate
- [ ] Ensure `docs/CHALLENGES.md` has Challenges **and** Learnings (B10)
- [ ] Copy `assignment-brief.pdf` into repo root
- [ ] Build deck from `docs/PRESENTATION.md`
- [ ] Dry-run 15-minute talk twice; cut to time
- [ ] Push / publish GitHub repo (when Abdul approves; local commits until then)
- [ ] Draft submission email (Gmail draft card; do not send until asked)

---

## 3. Product definition (short)

### Problem
Security teams drown in ASM and exposure findings (open cameras, PeopleSoft surface, username OSINT) with no trusted triage loop. Analysts lack graph context across related assets and cannot safely give an agent broad agency.

### Users
- Primary: Security analyst / ASM operator (demo persona)
- Secondary: Security lead reviewing HITL decisions
- Buyer narrative: DataRobot PS customer in a regulated industry

### Agent behavior
1. Ingest or select a finding in tenant scope  
2. Retrieve GraphRAG neighborhood (related hosts, services, prior findings, owners)  
3. Rank risk with explicit factors  
4. Draft remediation steps (non-destructive guidance only)  
5. Checker verifies citations + scope + no destructive verbs  
6. Human approves, rejects, or escalates — agent never “fixes” production itself  

### Non-goals
- No offensive exploit PoCs, payloads, or unauthorized scanning  
- No live CBUAE / customer production targeting in this repo  
- No OmniRoute model changes on abdul-ai  
- No auto-publish of remediations to ticketing without HITL  

---

## 4. GraphRAG plan

**Why:** Findings are relational (host → camera → default creds → same subnet → owner). Pure vector RAG misses multi-hop “what else is exposed near this?”

**Approach (v1, demo-ready):**
- **Graph:** nodes = Asset, Finding, CVE/Weakness, Owner, Segment; edges = `HAS_FINDING`, `RUNS_ON`, `SAME_SEGMENT`, `OWNED_BY`, `RELATED_CVE`
- **Store:** SQLite + edge table (or NetworkX persisted) for portability; optional Neo4j later
- **Vectors:** embed finding titles + remediation docs (local or gateway embeddings) for hybrid retrieve
- **Retrieve:** entity-link finding → k-hop subgraph → serialize as context → LLM ranks/drafts with citations to node ids
- **Eval:** retrieval hit-rate on seeded multi-hop questions (e.g. “which other cameras share this segment?”)

**Feasibility:** Yes for demo. Keep graph small (≤500 nodes) for 15-minute reliability.

---

## 5. Evaluation criteria (detailed)

### E1 — Functional demo
| Metric | Pass |
|--------|------|
| Cold start to UI | ≤ 60 s on demo machine |
| End-to-end triage (one finding) | ≤ 45 s wall time |
| Scope refusal on cross-tenant prompt | 100% of test cases |
| Destructive action request | Always refused + logged |

### E2 — Agent quality (seed set n≥20)
| Metric | Pass |
|--------|------|
| Risk rank within ±1 band of gold label | ≥ 80% |
| Remediation cites ≥1 graph node id | ≥ 90% |
| Hallucinated asset id rate | ≤ 5% |
| Checker catch of missing citation | ≥ 95% |

### E3 — GraphRAG
| Metric | Pass |
|--------|------|
| Multi-hop question accuracy (seed) | ≥ 75% |
| Latency p50 retrieve | ≤ 500 ms local |

### E4 — Engineering hygiene
| Metric | Pass |
|--------|------|
| Backend tests | Green CI |
| Frontend build | Clean production build |
| Secrets | None in git; `.env.example` only |
| Defensive-only tools | Review checklist signed |


### E6 — AI Engineer competencies (role fit)
| Metric | Pass |
|--------|------|
| Prompt prefix is stable across turns in a session | Documented + verified in one trace dump |
| Cache/token fields present on ≥1 successful run log | Fields non-null when provider reports them; else explicitly "provider N/A" |
| Eval harness runs on seed set in CI or `make eval` | Exit 0 on gold set |
| Architecture doc names alternatives rejected | ≥4 decisions with "why not X" |
| Model strategy states fine-tune trigger | Written threshold (e.g. risk-rank accuracy plateau) |

### E5 — Presentation / PS fit
| Metric | Pass |
|--------|------|
| Talk length | 13–15 minutes |
| Live demo success | 2/2 dry runs |
| Productize story | Names DR monitoring + template reuse |

---

## 6. Stack (proposed)

| Layer | Choice | Notes |
|-------|--------|-------|
| Agent | LangGraph + Pydantic | Code-first; POC loop |
| API | FastAPI | DataRobot-friendly |
| UI | React + Vite | Impeccable / Taste / ui-ux-pro-max |
| Tools | MCP server | Discoverable tools |
| GraphRAG | SQLite graph + embeddings | Portable demo |
| Observability | OpenTelemetry → DR external agent monitoring | Stub OK for interview |
| LLM | Configurable (OpenAI / DR gateway / local via env) | Document in README; no OmniRoute edits |
| Packaging | Docker Compose + optional `dr` scripts | Local-first |

---

## 7. Roles

| Role | Agent | Owns |
|------|-------|------|
| Product Manager | @Maria Hill (or DR-PM teammate) | PRD, demo script, presentation narrative, acceptance |
| AI Engineer | @Rhodey (or DR-AI-Eng teammate) | agent_spec, graph, LangGraph, API, evals, OTel |
| Design | Echo + Impeccable / Taste / ui-ux-pro-max skills | UI system, critique |
| Security review | @Nick Fury | Scope guards, defensive-only tool review |
| Coordinator | Tony Stark · VP | Checklist, blockers, DataRobot skills path |

---

## 8. ThreatAI reuse (local knowledge, not a fork)

Reuse patterns and **synthetic** shapes from ThreatAI work already done (exposed-camera ASM, PeopleSoft surface checks, Sherlock username OSINT, AI agent permission ideas). This repo stays self-contained with demo fixtures. Do not bind to live tenant data or push secrets.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| abdul-ai Wi-Fi drops | Scaffold on Origin/cloud; sync to `~/projects/DataRobot-AI` when online |
| LLM non-determinism (Haddix lesson) | Checker + retries; gold eval set; show 2–3 runs in demo |
| Scope creep | Non-goals locked; PM acceptance gate |
| Design looks “AI generic” | anti-ai-ui-tells + Taste + Impeccable required before FE freeze |
| GraphRAG over-engineering | Cap at SQLite+k-hop for v1 |
| No token/cache metrics (interview gap) | Ship C1 meters in agent trace even if provider returns 0 cached |

---

## 10. Immediate next actions

1. [ ] Land this file at `~/projects/DataRobot-AI/PLAN.md` on abdul-ai  
2. [ ] Spin PM + AI Engineer workstreams against Phase A  
3. [ ] Scaffold repo (FE+BE+agent) from `agent_spec` after PM PRD  
4. [ ] Seed GraphRAG + eval harness  
5. [ ] Design pass → FE  
6. [ ] Deck + dry-run  

---

## 11. Acceptance for “plan done”

- [x] Checklist exists covering every brief point (B1–B9) with eval criteria  
- [x] GraphRAG called out as feasible with concrete v1 approach  
- [x] Design skills named (Impeccable, UI UX Pro Max, Taste, anti-AI-UI-tells)  
- [x] PM + AI Eng ownership clear  
- [ ] Folder present on abdul-ai under `~/projects/DataRobot-AI`  
- [ ] Abdul OK to proceed to scaffold  

---

*Local commits only until Abdul says push. No third-party email without ask. Defensive security only.*
