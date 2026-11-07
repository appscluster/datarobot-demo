"""One readable line per agent step, for the desk console."""
from __future__ import annotations

from typing import Any, Dict


def describe(event: Dict[str, Any]) -> str:
    phase = event.get("phase")
    result = event.get("result") if isinstance(event.get("result"), dict) else {}
    if phase == "graph":
        return "LangGraph started. The nodes are planner, operator, and checker."
    if phase == "planner":
        verdict = event.get("verdict") if isinstance(event.get("verdict"), dict) else {}
        if verdict.get("allowed"):
            return "LangGraph planner allowed the request. It stays in this tenant."
        reason = str(verdict.get("reason") or "refused").replace("_", " ")
        return f"LangGraph planner refused the request. Reason: {reason}."
    if phase == "operator" and event.get("tool") == "enrich_asset_graph":
        nodes = int(result.get("subgraph_nodes") or 0)
        edges = int(result.get("subgraph_edges") or 0)
        retrieval = str(result.get("retrieval") or "SQLite GraphRAG")
        return f"{retrieval} returned {nodes} nodes and {edges} edges."
    if phase == "operator" and event.get("tool") == "rank_risk":
        band = str(result.get("band") or "unknown")
        return f"The operator ranked this case {band}."
    if phase == "operator" and event.get("tool") == "draft_remediation":
        model = str(result.get("model") or "the model")
        cited = int(result.get("cited_count") or 0)
        return (
            f"LangChain Core built the prompt. OmniRoute model {model} drafted the reply "
            f"and cited {cited} graph ids."
        )
    if phase == "metrics":
        metrics = event.get("metrics") if isinstance(event.get("metrics"), dict) else {}
        prompt = int(metrics.get("prompt_tokens") or 0)
        completion = int(metrics.get("completion_tokens") or 0)
        return f"Measured tokens: {prompt} prompt, {completion} completion."
    if phase == "checker":
        if result.get("passed"):
            return "LangGraph checker passed the draft."
        issues = result.get("issues") if isinstance(result.get("issues"), list) else []
        detail = ", ".join(str(item) for item in issues) or "the draft failed the check"
        return f"LangGraph checker rejected the draft. {detail}."
    if phase == "monitoring":
        if result.get("exported"):
            return "OpenTelemetry sent span casework.run to DataRobot."
        return "OpenTelemetry recorded span casework.run. Nothing was exported."
    if event.get("final"):
        return "The run finished. The draft is waiting for a person. Nothing was sent."
    return ""
