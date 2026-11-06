# Model strategy: gateway first, fine-tune only on evidence (PLAN §1b C3)

**Owner:** DR-AI-Eng · **Date:** 2026-11-05 (Asia/Dubai) · **v1 decision:** **No fine-tuning in the v1 demo.**

## v1: frontier model via DataRobot LLM Gateway

- Model placeholder: `datarobot/anthropic/claude-sonnet-4-5-20250929`. Confirm with `list_llm_models.py` after `dr auth login`. Not yet verified.
- Env-configurable model id (gateway, deployed LLM via `llm_deployment_id`, or a local endpoint). No OmniRoute changes.
- Recorded-run fallback for offline dry runs.
- Risk band is computed by deterministic `rank_risk` factors. The LLM explains and drafts. This keeps the part we would most want to fine-tune measurable from day one.

## Where a small model could pay off

The agent loop calls the LLM 3–6 times per triage. Two of those calls are narrow, high-volume classification tasks:

| Candidate | Task | Why it fits a small model | Training data source |
|-----------|------|---------------------------|----------------------|
| **Risk-ranker** | finding + subgraph features → band (5 classes) + factor rationale | Fixed label space, structured input, needs to be consistent | Gold bands (evals) + approved HITL decisions over time |
| **Citation checker** | draft + subgraph → {pass, missing_citation, invalid_id, unsafe_language} | Binary/multi-label check run on every draft. Latency and cost matter | Checker logs + injected-failure eval cases |

Base: a local **Qwen** small instruct model (e.g. 1.5–7B class) with LoRA, served beside the agent. A DataRobot-hosted small model deployment is an option.

## Fine-tune trigger (all must hold)

1. **Plateau:** risk-rank ±1-band accuracy on the gold set stops improving (<2 pts gain) across 3 prompt or factor iterations. Or checker catch rate on injected failures stays below the 95% E2 bar.
2. **Data:** ≥500 labelled examples (gold + human-approved decisions). The v1 gold set of n=20 is far too small, which is a reason not to fine-tune now.
3. **Economics:** the narrow step accounts for ≥30% of per-triage `usd_estimate` or p50 latency (from PROMPT_CACHE meters), even after caching.
4. **Eval parity gate:** the fine-tuned model must match or beat the gateway model on the held-out gold split *and* pass 100% of scope-refusal evals before it can be swapped in behind the same tool interface.

## Why not in v1

- Too little data. Fine-tuning on 20 synthetic findings would overfit and prove nothing.
- The interview goal is a credible loop, evals, and governance (B13, B15). A fine-tune would add risk to the demo without a measurable gain.
- The architecture keeps the option open. `rank_risk` and the Checker are separate nodes with typed I/O, so a small model can replace either one without touching the graph.

## Talk track (30 s, Productize section)

"We start with a governed gateway model. We have instrumented exactly two narrow steps, risk ranking and citation checking, with evals and cost meters. When accuracy plateaus and those steps dominate cost, we fine-tune a small local model for them and gate the swap on the same evals. We don't fine-tune just because we can."
