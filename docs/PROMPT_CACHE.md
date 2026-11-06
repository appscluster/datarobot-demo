# Prompt caching and token economics (PLAN §1b C1)

**Owner:** DR-AI-Eng · **Date:** 2026-11-05 (Asia/Dubai) · **Status:** Design intent (not yet implemented)

## Goal

Each triage run reuses one cached prefix across planner, operator, and checker calls, and across findings in the same session. Every run logs its own token and cost meters so we can say, during the demo, "this is the cache hit ratio on the second finding in this session."

## Message layout

| Order | Block | Stability | Cache |
|-------|-------|-----------|-------|
| 1 | `system_prompt` (from `agent_spec.md`) | Frozen per release | Prefix |
| 2 | Tool schemas (7 tools, sorted by name, canonical JSON) | Frozen per release | Prefix |
| 3 | Tenant/policy block: `tenant_id`, scope rules version, destructive-rule list hash, risk-band definitions | Frozen per session | Prefix (cache breakpoint here) |
| 4 | Finding record + serialized subgraph | Per finding | Not cached |
| 5 | Conversation turns + tool results | Per call | Not cached |

Rules:
- Blocks 1–3 must be byte-identical across calls: no timestamps, run ids, or random ordering in them. Put dates and ids in block 4 or later.
- Tool schemas are serialized with sorted keys. If the schema hash changes, the release gets a version bump and the eval gate reruns (see `evals/`).
- If the provider supports explicit cache markers (for example Anthropic `cache_control`), set one breakpoint after block 3. If the gateway only does automatic prefix caching, the same ordering still applies.
- The prefix should be over the provider's minimum cacheable length. Pad it with policy text, not filler.

## Metrics (required on every LLM call and rolled up per run)

| Field | Source | Notes |
|-------|--------|-------|
| `prompt_tokens` | provider `usage` | Input tokens including cached |
| `cached_tokens` | provider `usage` (cache read) | `null` if gateway does not report → flag `cache_metrics_unavailable` |
| `completion_tokens` | provider `usage` | |
| `cache_hit_ratio` | `cached_tokens / prompt_tokens` | Per call and per run (token-weighted) |
| `usd_estimate` | `config/pricing.yaml` × tokens (cached tokens at the cache-read rate) | Estimate only. Prices sit in config, never hard-coded |
| `model`, `run_id`, `tenant_id`, `node` (planner/operator/checker), `latency_ms` | runtime | |

Where the meters show up:
- **Run log / SQLite `llm_calls` table**: one row per call. The `runs` table holds the rollup.
- **OpenTelemetry**: span attributes `llm.prompt_tokens`, `llm.cached_tokens`, `llm.cache_hit_ratio`, `llm.usd_estimate` on each LLM span. Run-level totals go on the root span. This is the path to DataRobot external-agent monitoring.
- **UI**: the trace header shows run cost and cache ratio. Each LLM step shows its own meters. The queue footer shows the session total.

## Expected behaviour (demo talking point)

- First finding in a session: low hit ratio on the first call, then high on the operator and checker calls.
- Second finding (for example F-105 after F-101): blocks 1–3 hit the cache from the first call, so the ratio should be clearly higher. If it is not, the prefix is unstable and that counts as a bug.

## Eval and guard hooks

- `evals/` includes a prefix-stability check: render blocks 1–3 twice for one session and assert they are byte-equal.
- Run reports include median `cache_hit_ratio` and `usd_estimate` per triage alongside E2 metrics. This is informational, not a pass bar for v1.

## Open items

- Confirm whether the DataRobot LLM Gateway returns cache-read token counts for the chosen model after `dr auth login` and model confirmation (`list_llm_models.py`).
- Pricing values for `config/pricing.yaml`: fill from the provider price sheet at build time and label them as estimates.
