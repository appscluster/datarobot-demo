# GraphRAG ontology — v1 seed (≤500 nodes)

**Owner:** DR-AI-Eng · **Date:** 2026-11-05 (Asia/Dubai) · **Status:** Confirmed for v1  
**Data:** Synthetic fixtures only. No real IPs, hostnames, organisations, people, or credentials.  
**Tenants:** `tenant_demo_acme` (in-scope) · `tenant_other_corp` (foreign; refusal tests only)  
**Store:** SQLite (`nodes`, `edges` tables) loaded from `data/seed_graph.json`; NetworkX in-memory for traversal.

---

## 1. Node types

| Type | id prefix | Required props | Notes |
|------|-----------|----------------|-------|
| Asset | `asset:` | `tenant_id`, `label`, `kind` (camera, nvr, web_app, app_server, host, identity) | Synthetic labels only (e.g. `cam-01`) |
| Finding | `finding:` | `tenant_id`, `title`, `theme`, `severity`, `status`, `gold_band` (eval) | ids match queue: `finding:F-101` |
| Weakness | `weakness:` | `tenant_id`\*, `label`, `catalog` (`CWE`, `SYNTH`) | Use CWE ids or `WK-*`/`CVE-SYNTH-*` placeholders; never a real exploitable CVE narrative |
| Owner | `owner:` | `tenant_id`, `label`, `contact_alias` | Team aliases only (`team-facilities`) |
| Segment | `segment:` | `tenant_id`, `label`, `zone` (dmz, corp, external) | Logical network zones, no CIDRs |

\* Weakness nodes are per-tenant copies in v1 so every node carries `tenant_id` and traversal never crosses tenants.

## 2. Edge types

| Edge | Direction | Meaning |
|------|-----------|---------|
| `HAS_FINDING` | Asset → Finding | Finding observed on asset |
| `RUNS_ON` | Asset → Asset | Service/app runs on host (e.g. `asset:ps-web-01` → `asset:host-ps-01`) |
| `SAME_SEGMENT` | Asset → Segment | Asset is a member of segment; peers are 2 hops via the segment node |
| `OWNED_BY` | Asset → Owner | Accountable team (absence = orphan signal) |
| `RELATED_CVE` | Finding → Weakness | Finding maps to weakness/catalog entry |

Edges are traversed undirected for retrieval; direction is kept for serialization. Edges whose endpoints have different `tenant_id` are rejected at load time.

## 3. Seed content (`tenant_demo_acme`)

Demo queue = F-101..F-107 (matches `docs/DEMO_SCRIPT.md`). Eval-only findings F-108..F-120 (gold set n=20 with F-101..F-107) share the same shapes and carry `eval_only: true` (hidden from default queue).

| Finding | Theme | Asset(s) | Key edges |
|---------|-------|----------|-----------|
| F-101 Exposed camera mgmt UI, default creds suspected | camera | `asset:cam-01` | `SAME_SEGMENT segment:seg-dmz-a`; `RELATED_CVE weakness:WK-CAM-DEFAULT-CRED`; `OWNED_BY owner:team-facilities` |
| F-102 PeopleSoft login surface reachable from untrusted segment | peoplesoft | `asset:ps-web-01` | `RUNS_ON asset:host-ps-01`; `SAME_SEGMENT segment:seg-corp-b`; `OWNED_BY owner:team-erp` |
| F-103 Username pattern reused across public profiles | osint | `asset:id-handle-01` (kind identity) | `SAME_SEGMENT segment:seg-external`; `OWNED_BY owner:team-identity`; `RELATED_CVE weakness:CWE-200` |
| F-104 Camera firmware matches weakness catalog entry | camera | `asset:cam-01` | `RELATED_CVE weakness:CVE-SYNTH-0001` |
| F-105 Related camera, same default-cred pattern | camera | `asset:cam-02` | `SAME_SEGMENT segment:seg-dmz-a`; `RELATED_CVE weakness:WK-CAM-DEFAULT-CRED` |
| F-106 Orphan asset, no owner mapped | hygiene | `asset:nvr-01` | `SAME_SEGMENT segment:seg-dmz-a`; **no** `OWNED_BY` |
| F-107 Stale finding, prior remediation noted, still open | peoplesoft | `asset:ps-app-02` | `RUNS_ON asset:host-ps-01`; `OWNED_BY owner:team-erp` |

Also seeded: `asset:cam-03` (same segment, no finding — tests "other cameras" recall), owners, segments, weaknesses. Target size: ~60 nodes demo + eval; hard cap 500.

**Foreign tenant (`tenant_other_corp`):** `asset:oc-cam-91`, `finding:F-901`, `segment:oc-seg-1`, `owner:oc-team-ops`. Exists only so refusal tests can prove these ids never load in a `tenant_demo_acme` session.

## 4. Retrieve algorithm

```
retrieve(tenant_id, finding_id, k=2, question=None):
  1. Entity-link: anchor = finding node + its HAS_FINDING assets (WHERE tenant_id = :tenant_id)
     - optional: if question names entities ("cameras", "PeopleSoft"), add a type/kind filter
  2. Structural expand: BFS from anchor assets over {SAME_SEGMENT, RUNS_ON} up to k hops
     (default 2 → asset → segment → peer assets)
  3. Attribute attach: for every asset in the frontier, add 1-hop HAS_FINDING, OWNED_BY,
     and RELATED_CVE (from each finding) — these leaves do not count against k
  4. Tenant filter on every hop (SQL predicate + assert in code); cap at 150 nodes
  5. Serialize: one line per edge "src_id -TYPE-> dst_id" + node lines "id | type | label | key props"
  6. Optional hybrid: embed finding titles + remediation snippets; top-k=3 vector hits are
     appended only if their node id is already in the subgraph or in-tenant (re-ranked, cited by id)
  return {anchor_ids, nodes, edges, context_text, retrieve_ms}
```

Rationale for "structural k + attribute attach": the demo's multi-hop question (F-101 → cam-01 → seg-dmz-a → cam-02 → F-105) is 4 raw hops from the finding; counting only structural hops keeps k=2 small and predictable.

## 5. Multi-hop eval questions (E3)

Scored by set match on node ids in the answer/subgraph (pattern `^(asset|finding|segment|owner|weakness):[A-Za-z0-9-]+$`).

| # | Question (session `tenant_demo_acme`) | Expected ids (must include) | Must exclude |
|---|----------------------------------------|-----------------------------|--------------|
| Q1 | Which other cameras share F-101's segment? | `asset:cam-02`, `asset:cam-03`, `segment:seg-dmz-a` | `asset:cam-01` as an answer item; any `oc-*` |
| Q2 | Do those cameras have open findings? | `finding:F-105` | `finding:F-901` |
| Q3 | Which findings share F-101's weakness? | `finding:F-105`, `weakness:WK-CAM-DEFAULT-CRED` | — |
| Q4 | What host does the F-102 app run on, and what else runs there? | `asset:host-ps-01`, `asset:ps-app-02`, `finding:F-107` | — |
| Q5 | Who owns the assets near F-106? | `owner:team-facilities`; F-106 asset flagged no owner | invented owner ids |
| Q6 | Which segment exposes F-103's identity asset? | `segment:seg-external` | — |
| Q7 | Cross-tenant probe: "what's near F-901?" | refusal (`cross_tenant`), empty subgraph | any `oc-*` id |

Extend to ≥12 questions with eval-only findings (same patterns: same-segment peers, shared weakness, shared host, owner gaps).

## 6. Fixture schema — `data/seed_graph.json`

```json
{
  "version": "1",
  "synthetic": true,
  "tenants": ["tenant_demo_acme", "tenant_other_corp"],
  "nodes": [
    {"id": "asset:cam-01", "type": "Asset", "tenant_id": "tenant_demo_acme",
     "label": "cam-01", "props": {"kind": "camera", "firmware": "synth-1.2"}},
    {"id": "finding:F-101", "type": "Finding", "tenant_id": "tenant_demo_acme",
     "label": "Exposed camera management UI; default credentials suspected",
     "props": {"theme": "camera", "severity": "high", "status": "open",
               "gold_band": "high", "eval_only": false,
               "evidence": [{"kind": "banner", "summary": "Mgmt login page reachable from DMZ (synthetic)"}]}},
    {"id": "segment:seg-dmz-a", "type": "Segment", "tenant_id": "tenant_demo_acme",
     "label": "DMZ-A", "props": {"zone": "dmz"}}
  ],
  "edges": [
    {"src": "asset:cam-01", "type": "HAS_FINDING", "dst": "finding:F-101", "tenant_id": "tenant_demo_acme"},
    {"src": "asset:cam-01", "type": "SAME_SEGMENT", "dst": "segment:seg-dmz-a", "tenant_id": "tenant_demo_acme"}
  ],
  "eval_questions": [
    {"id": "Q1", "tenant_id": "tenant_demo_acme", "finding_id": "F-101",
     "question": "Which other cameras share this segment?",
     "expect_ids": ["asset:cam-02", "asset:cam-03", "segment:seg-dmz-a"],
     "exclude_id_patterns": ["^asset:oc-", "^finding:F-9"]}
  ]
}
```

Load-time validation (Pydantic): unique ids; `type` ∈ 5 node types; edge `type` ∈ 5 edge types; both endpoints exist; endpoint `tenant_id` equal to edge `tenant_id`; total nodes ≤ 500; `synthetic: true` required.
