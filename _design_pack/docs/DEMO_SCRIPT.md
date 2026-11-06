# Demo script — ThreatAI Security Analyst Agent (5 minutes)

**Slot:** Live demo inside the 15-minute talk (~minutes 5:00–10:00).  
**Data:** Synthetic demo tenant only. Defensive framing — no payloads, no scanning instructions, no production targeting.  
**Note:** LLM runs are non-deterministic. Prefer showing **two short runs** or one **cached/recorded run** plus one live attempt so the checker and refusals still land.

---

## Pre-demo checklist

- [ ] App started with primary entrypoint `docker compose up` (optional `dr run dev` OK if documented).
- [ ] Seed loaded: demo tenant `tenant_demo_acme` with findings F-101..F-107 (see seed list below).
- [ ] LLM key / gateway set in `.env` (or recorded/cached offline fallback enabled).
- [ ] Offline fallback ready: recorded run JSON or screen recording of happy path + refusals.
- [ ] Browser tabs: (1) app UI on localhost, (2) optional agent trace/network quiet, (3) this script or speaker notes.
- [ ] Cold start timed once today: UI reachable ≤ 60 s (E1).
- [ ] Second terminal ready to tail audit log if asked.
- [ ] No live customer / CBUAE data in the session.

## Seeded demo findings (synthetic)

Tenant: `tenant_demo_acme` (≈6–7 findings shown in queue).

| ID | Title (defensive) | Intent in demo |
|----|-------------------|----------------|
| F-101 | Exposed IP camera management UI; default credentials suspected | Primary pick; GraphRAG “other cameras on segment” |
| F-102 | PeopleSoft login surface reachable from untrusted segment | Secondary context / risk factors |
| F-103 | OSINT: username pattern reused across public profiles | Enrichment / identity hygiene narrative |
| F-104 | Camera firmware version matches known weakness catalog entry | CVE/weakness node citation |
| F-105 | Related camera on same segment; same default-cred pattern | Multi-hop GraphRAG proof |
| F-106 | Orphan asset: no owner mapped | Escalation path optional |
| F-107 | Stale finding: prior remediation noted, still open | Checker / rank factors |

Foreign tenant for refusal: `tenant_other_corp` (e.g. `finding:F-901`, `asset:oc-cam-91` — must not load under demo session).

---

## Timed beats (5:00 total)

### 0:00–0:30 — Queue

- **On screen:** Findings queue for `tenant_demo_acme`; severity/status columns; F-101 near top.
- **Say:** “Analysts drown in exposure findings. Here’s a seeded tenant queue — cameras, a PeopleSoft surface, OSINT username reuse. We never leave this tenant.”
- **Expect:** Queue loads; tenant badge visible; no foreign findings.

### 0:30–1:00 — Pick a finding

- **On screen:** F-101 detail — evidence summary, asset id, segment label (synthetic).
- **Say:** “We pick the exposed camera with suspected default credentials. The agent will enrich from the asset graph, not from live scanning.”
- **Expect:** Detail pane + “Run triage” control enabled.

### 1:00–2:00 — Agent trace (planner → operator → checker)

- **On screen:** Live step trace: Planner plan → Operator tool calls with **`check_scope` first**, then `get_finding`, `enrich_asset_graph`, `rank_risk`, `draft_remediation` → Checker pass/fail. Scope middleware also wraps every tool call with `tenant_id`.
- **Say:** “Code-first LangGraph loop: planner, operator, checker. Scope is checked first — and again on every tool — before we enrich or draft. Tools are MCP, tenant-scoped, defensive only.”
- **Expect:** Trace shows `check_scope` (or equivalent scope verdict) before enrichment/draft tools; steps stream or poll; wall time on path to ≤ 45 s for full triage (E1).

### 2:00–2:45 — GraphRAG neighborhood

- **On screen:** Graph panel: F-101 → asset → `SAME_SEGMENT` → F-105 (and related camera nodes); node ids labeled.
- **Say:** “GraphRAG answers multi-hop questions — which other cameras share this segment? Pure vector RAG often misses that.”
- **Expect:** Neighborhood shows ≥1 related camera on the same segment; node ids visible.

### 2:45–3:30 — Risk rank + remediation draft

- **On screen:** Risk band with explicit factors (exposure, default-cred signal, segment blast radius, owner gaps). Remediation draft with citations like `asset:cam-01`, `segment:seg-dmz-a`, `finding:F-105`.
- **Say:** “Risk is ranked with factors you can argue with. Remediation is guidance only — change defaults, restrict management UI, assign owner — and every claim cites a graph node.”
- **Expect:** ≥1 node-id citation in the draft; no exploit steps; no “run this payload” language.

### 3:30–4:00 — Human approve

- **On screen:** HITL bar: Approve / Reject / Escalate.
- **Say:** “Human in the loop. The agent does not fix production. I approve the draft for the backlog.”
- **Expect:** Decision recorded; audit entry with run id, tenant, finding, decision=`approve`.

### 4:00–4:45 — Refusal path (two cases)

- **On screen:** Chat or action prompt.
- **Case A — cross-tenant:** Ask to open or triage a finding under `tenant_other_corp`.
  - **Say:** “Out of tenant — refuse.”
  - **Expect:** Hard refusal; audit reason `cross_tenant`; no graph load for foreign tenant.
- **Case B — destructive:** “Go fix it / shut the camera down in prod.”
  - **Say:** “Destructive and out of agency — refuse and log.”
  - **Expect:** Refusal; audit reason `destructive_request`; no mutating tool call.

### 4:45–5:00 — Close demo beat

- **On screen:** Audit snippet or decision history.
- **Say:** “Happy path, citations, HITL, and refusals — that’s the governed loop we’ll productize on DataRobot.”
- **Expect:** Return to talk (challenges / productize slides).

---

## If it breaks (fallback)

1. **LLM timeout / bad plan:** Switch to cached/recorded run for F-101; narrate the same beats from the recording; still click HITL on a pre-seeded result if UI allows.
2. **UI won’t start:** Re-try `docker compose up`; if still down, show architecture slide + GraphRAG screenshot from dry run; play 60–90 s screen recording of queue → triage → refuse.
3. **Graph empty:** Re-run seed script once; if still empty, use static mermaid/screenshot of neighborhood and continue to risk/remediation from fixture JSON.
4. **Refusal doesn’t fire:** Show unit-test output or audit fixture proving `check_scope` rejects cross-tenant and destructive verbs; do not improvise a live bypass.
5. **Time overrun:** Skip secondary finding F-102 narrative; keep GraphRAG + one refusal minimum.

## Non-determinism note (say aloud if needed)

“Agent outputs vary run to run. We mitigate with a checker, a gold eval set, and in demos we show two runs or a cached path so the refusal and citation contracts stay visible.”
