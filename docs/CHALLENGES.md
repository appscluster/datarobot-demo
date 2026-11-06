# Challenges & Learnings — ThreatAI Security Analyst Agent

**Maps to:** Brief B5, B10; presentation §6  
**Rule:** Honest obstacles + what we changed because of them. Defensive product only; synthetic data.

---

## Challenges (each with mitigation)

| # | Challenge | Why it hurts | Mitigation chosen |
|---|-----------|--------------|-------------------|
| 1 | LLM non-determinism | Same finding, different ranks/drafts; demo and customers lose trust | Checker node + retries; gold eval set (E2); show 2 runs or a cached path in the talk |
| 2 | Scope enforcement | Cross-tenant bleed or “go fix prod” destroys the regulated-buyer story | `tenant_id` on every tool; `check_scope`; refuse + audit; Security sign-off on tool inventory |
| 3 | GraphRAG freshness / complexity | Stale or huge graphs break the 15-minute demo | Cap ≤500 synthetic nodes; SQLite k-hop for v1; Neo4j deferred |
| 4 | HITL latency | Humans are slower than models; blocking UX kills triage throughput | Persist approve/reject/escalate; demo uses immediate click; product path is async decide-later |
| 5 | Token cost without cache discipline (interview product gap) | Re-sending full system+tools every hop wastes $ at PS scale | Frozen prompt prefix; track `cache_hit_ratio` / tokens / `usd_estimate`; **target ≥ 60%** hit on 2nd+ finding when provider reports cache |

---

## Learnings (B10)

1. **Agency without tenancy and evals is a liability.** Build refusal tests and the gold set before adding clever tools — the checker and CI gate are product features, not polish.
2. **Citations to graph node ids beat fluent prose.** Analysts and auditors argue with ids; hallucinations show up as unknown node ids in eval.
3. **Prompt structure is a cost feature.** Putting system + tool schemas + tenant graph context in a stable prefix (finding last) is how we show AI-engineering maturity on caching — meters belong in the trace on day one.
4. **A working vertical slice beats a fake production claim.** The PDF is explicit: not expecting production-ready software. Say the scope out loud; invest in demo reliability, defended architecture, and the productization path instead.

---

## Talk cue

Spend ~1:30 on Challenges & Learnings together (see `docs/PRESENTATION.md` timing table). Do not skip Learnings — B10 requires both.
