# PM acceptance gate — ThreatAI Security Analyst Agent (v1)

**Purpose:** Single checklist mapping brief requirements B1–B15 and eval criteria E1–E6 to owner and verification.  
**Rule:** No Phase G submission until every row below is Pass or explicitly Waived by Abdul with reason.  
**Data:** Synthetic demo only. Defensive security product — no exploit payloads, scanning instructions, or offensive framing.  
**Scope honesty (B15):** Working demo prototype + productization path — **not** production-ready software.

---

## B1–B9 — Brief requirements (core build)

| ID | Requirement (summary) | Owner | Verification method | Pass? |
|----|----------------------|-------|---------------------|-------|
| B1 | Functioning full app (FE + BE) | AI Eng + Design | Primary: `docker compose up` (optional `dr run dev`); queue UI loads; one E2E triage completes | [ ] |
| B2 | Code-first (LangGraph / Pydantic / etc.) | AI Eng | Agent graph is Python; Pydantic schemas validate; unit tests cover planner/operator/checker edges | [ ] |
| B3 | 15-minute presentation covers problem, solution, architecture | PM | Dry-run ≤15 min; each section in `docs/PRESENTATION.md` has slide + spoken script | [ ] |
| B4 | Live demo in the presentation | PM + AI Eng | Follow `docs/DEMO_SCRIPT.md`; happy path + refusal path; works without live internet except LLM (or cached run) | [ ] |
| B5 | Call out challenges honestly | PM | ≥3 challenges with chosen mitigations in `docs/CHALLENGES.md` + PRESENTATION §6 | [ ] |
| B6 | Vision for DR customers + productize | PM | Narrative names PS buyer, governance/audit, template reuse, OTel → DR monitoring (PRESENTATION §7; `docs/PRODUCTIZE.md` when written) | [ ] |
| B7 | Submit GitHub code + deck by email | PM + Coordinator | Repo README + deck file exist; submission email **drafted only** until Abdul asks to send | [ ] |
| B8 | Maps to DataRobot PS / customer value | PM | Story fits regulated ASM triage, HITL, audit; aligned to AI Engineer–PS role | [ ] |
| B9 | Prefer DR agent skills / platform path | AI Eng | `agent_spec.md` present; OTel hooks stubbed; LLM path documented in README | [ ] |

---

## B10–B15 — PDF-verified interview expectations

| ID | Requirement (summary) | Owner | Verification method | Pass? |
|----|----------------------|-------|---------------------|-------|
| B10 | Challenges **and** Learnings | PM | `docs/CHALLENGES.md` has ≥3 challenges each paired with learning themes; PRESENTATION §6 speaks both | [ ] |
| B11 | Problem-Solving Acumen | PM | PRD problem ≤½ page, crisp ASM inefficiency; opening script names the inefficiency | [ ] |
| B12 | Strategic Vision | PM | PRESENTATION productize + model strategy; buyer → template → DR monitoring path clear | [ ] |
| B13 | Technical Credibility | PM + AI Eng | Live demo succeeds in dry-run; architecture trade-offs defended (PRESENTATION §3; later `ARCHITECTURE.md`) | [ ] |
| B14 | Creativity & Passion | PM + AI Eng | Demo shows GraphRAG neighborhood + HITL refusals + cost/cache line (or spoken target) | [ ] |
| B15 | Not production-ready (PDF) | PM + AI Eng | README + PRD non-goals state demo prototype scope; no “prod hardened” claims in deck | [ ] |

---

## E1–E6 — Evaluation criteria

### E1 — Functional demo

| Metric | Pass bar | Owner | Verification method | Pass? |
|--------|----------|-------|---------------------|-------|
| Cold start to UI | ≤ 60 s on demo machine | AI Eng | Timed `docker compose up` to UI ready (optional `dr run dev` path documented) | [ ] |
| End-to-end triage (one finding) | ≤ 45 s wall time | AI Eng | Stopwatch on seeded F-101 run | [ ] |
| Scope refusal on cross-tenant prompt | 100% of test cases | AI Eng + Security | Automated tests + demo Case A | [ ] |
| Destructive action request | Always refused + logged | AI Eng + Security | Automated tests + demo Case B; audit row present | [ ] |

### E2 — Agent quality (seed set n≥20)

| Metric | Pass bar | Owner | Verification method | Pass? |
|--------|----------|-------|---------------------|-------|
| Risk rank within ±1 band of gold | ≥ 80% | AI Eng | Eval harness on gold labels | [ ] |
| Remediation cites ≥1 graph node id | ≥ 90% | AI Eng | Eval harness citation check | [ ] |
| Hallucinated asset id rate | ≤ 5% | AI Eng | Compare cited ids to graph inventory | [ ] |
| Checker catch of missing citation | ≥ 95% | AI Eng | Inject citation-less drafts in tests | [ ] |

### E3 — GraphRAG

| Metric | Pass bar | Owner | Verification method | Pass? |
|--------|----------|-------|---------------------|-------|
| Multi-hop question accuracy (seed) | ≥ 75% | AI Eng | Seed questions e.g. “which other cameras share this segment?” | [ ] |
| Latency p50 retrieve | ≤ 500 ms local | AI Eng | Benchmark retrieve on demo machine | [ ] |

### E4 — Engineering hygiene

| Metric | Pass bar | Owner | Verification method | Pass? |
|--------|----------|-------|---------------------|-------|
| Backend tests | Green CI | AI Eng | CI or local pytest green | [ ] |
| Frontend build | Clean production build | Design + AI Eng | `npm run build` (or equiv) succeeds | [ ] |
| Secrets | None in git; `.env.example` only | Security + AI Eng | Secret scan / manual review | [ ] |
| Defensive-only tools | Review checklist signed | Security (Nick Fury) | Tool inventory review; no exploit/scan payloads | [ ] |

### E5 — Presentation / PS fit

| Metric | Pass bar | Owner | Verification method | Pass? |
|--------|----------|-------|---------------------|-------|
| Talk length | 13–15 minutes | PM | Two timed dry-runs against PRESENTATION timing table | [ ] |
| Live demo success | 2/2 dry runs | PM + AI Eng | Record outcomes; fallback plan exercised once | [ ] |
| Productize story | Names DR monitoring + template reuse | PM | Present in talk; checklist against PRESENTATION §7 | [ ] |
| Cost & quality beat present | Caching + eval gate spoken (~60–75s) | PM | Timing table §4 present in dry-run notes | [ ] |
| Model-strategy beat present | ~30s fine-tune trigger criteria | PM | PRESENTATION §7 model strategy spoken in dry-run | [ ] |

### E6 — AI Engineer competencies (role fit) — PLAN §5

| Metric | Pass bar | Owner | Verification method | Pass? |
|--------|----------|-------|---------------------|-------|
| Prompt prefix stable across turns in a session | Documented + verified in one trace dump | AI Eng | Trace shows frozen prefix ordering (system/tools/tenant; finding last) | [ ] |
| Cache/token fields on ≥1 successful run log | Fields non-null when provider reports them; else explicitly `provider_N/A` | AI Eng | Inspect run log / OTel attrs: `prompt_tokens`, `cached_tokens`, `cache_hit_ratio`, `usd_estimate` | [ ] |
| Cache hit ratio tracked | Metric logged; **target ≥ 60%** on 2nd+ finding when provider reports cache (target, not invented measurement) | AI Eng + PM | Meter present in trace/UI; target documented in PRD/PRESENTATION | [ ] |
| Cost per triage reported | Tokens + `usd_estimate` (or N/A) on each run | AI Eng | Run log sample attached to acceptance packet | [ ] |
| Eval harness / eval gate in CI | `make eval` or CI job exit 0 on gold set; prompt/agent changes must pass E2/E3 before merge | AI Eng | CI config or Makefile target + failing-change proof | [ ] |
| Architecture doc names alternatives rejected | ≥4 decisions with “why not X” | PM + AI Eng | PRESENTATION §3 table; later `docs/ARCHITECTURE.md` | [ ] |
| Model strategy states fine-tune trigger | Written threshold (narrow task + labels + cost/latency case) | AI Eng | `docs/MODEL_STRATEGY.md` or PRESENTATION §7 criteria | [ ] |

---

## Owner legend

| Owner | Agent / seat |
|-------|----------------|
| PM | Maria Hill / DR-PM |
| AI Eng | Rhodey / DR-AI-Eng |
| Design | Echo + Impeccable / Taste / ui-ux-pro-max |
| Security | Nick Fury |
| Coordinator | Tony Stark · VP (blockers, submission draft discipline) |

---

## Scope discipline — what we say no to for v1

PM acceptance gate will **reject** scope creep into:

1. Offensive exploit PoCs, payloads, or unauthorized scanning instructions.
2. Live CBUAE / customer production targeting or binding to live tenant data.
3. OmniRoute / abdul-ai model-routing changes.
4. Auto-publish of remediations to ticketing or change systems without HITL.
5. Graph backends beyond SQLite (+ optional NetworkX persist) unless AI Eng proves demo risk.
6. No-code-only agent builders as the primary implementation (code-first is the brief).
7. Feature work that breaks the 15-minute talk or the one-command local demo.
8. Real credential stores, real camera IPs, or any non-synthetic “proof” assets in the repo.
9. Claiming production-ready / hardened status (B15) — vertical slice + productization path only.
10. Fine-tuning a small model inside the interview demo unless Abdul explicitly expands scope (document the trigger only).

If a request is not in PLAN §3 agent behavior (six steps) or §6 stack, default answer is **no for v1** — park it for post-interview.

---

## Gate decision

- [ ] All B1–B15 rows Pass or Waived with written reason  
- [ ] All E1–E6 metric rows Pass or Waived with written reason  
- [ ] Security defensive-only checklist signed  
- [x] AI Eng sign-off on PRD Technical notes (DR-AI-Eng APPROVED 2026-11-05)  
- [ ] PM dry-run of presentation + demo complete (timing table held)  

**PM sign-off:** ______________________  Date: __________
