from __future__ import annotations
from typing import Any, Dict, List, TypedDict, Callable
import time

from . import graph as graph_mod
from . import checker as checker_mod
from . import scope as scope_mod

try:
    from langgraph.graph import StateGraph, START, END
    _HAS_LANGGRAPH = True
except Exception:
    _HAS_LANGGRAPH = False
    START = "__start__"
    END = "__end__"


class TriageState(TypedDict, total=False):
    tenant_id: str
    finding_id: str
    subgraph: Dict[str, Any]
    risk: Dict[str, Any]
    draft: Dict[str, Any]
    refused: bool
    refusal_reason: str
    steps: List[Dict[str, Any]]
    metrics: Dict[str, Any]


def _emit(sink: Callable[[Dict[str, Any]], None], event: Dict[str, Any]) -> None:
    if sink:
        sink(event)


def _planner(state: TriageState, sink: Callable[[Dict[str, Any]], None]) -> TriageState:
    # Check scope early
    v = scope_mod.check_scope(state["tenant_id"], "triage finding", [f"finding:{state['finding_id']}"])
    _emit(sink, {"phase": "planner", "verdict": v})
    if not v["allowed"]:
        state["refused"] = True
        state["refusal_reason"] = v["reason"]
    return state


def _operator(state: TriageState, sink: Callable[[Dict[str, Any]], None]) -> TriageState:
    if state.get("refused"):
        return state
    tenant_id = state["tenant_id"]
    finding_id = state["finding_id"]
    sub = graph_mod._ACTIVE_GRAPH.retrieve(tenant_id, finding_id, k=2, question=None) if graph_mod._ACTIVE_GRAPH else {"nodes": [], "edges": []}
    _emit(sink, {"phase": "operator", "tool": "enrich_asset_graph", "result": {"subgraph_nodes": len(sub.get("nodes", []))}})
    state["subgraph"] = sub
    # Rank risk (simple heuristic from node props)
    n = graph_mod._ACTIVE_GRAPH.get(f"finding:{finding_id}") if graph_mod._ACTIVE_GRAPH else None
    band = (n.props.get("gold_band") if n else "medium") if n else "medium"
    risk = {"band": band, "score": {"critical": 0.95, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.05}.get(band, 0.5), "factors": []}
    state["risk"] = risk
    _emit(sink, {"phase": "operator", "tool": "rank_risk", "result": risk})
    # Draft remediation
    evidence_ids = [n["id"] for n in sub.get("nodes", [])][:2] or [f"finding:{finding_id}"]
    text = (n.props.get("remediation") if n else None) or "Rotate default credentials and restrict the management UI to the admin segment."
    owner = (n.props.get("owner_id") if n else None) or "owner:team-facilities"
    steps = [{"text": text, "cites": evidence_ids, "owner_id": owner}]
    cited = sorted({c for s in steps for c in s["cites"]})
    draft = {"steps": steps, "summary": f"{band} risk; coordinate with the owning team.", "cited_ids": cited, "non_destructive": True}
    state["draft"] = draft
    _emit(sink, {"phase": "operator", "tool": "draft_remediation", "result": {"cited_count": len(cited)}})
    return state


def _checker(state: TriageState, sink: Callable[[Dict[str, Any]], None]) -> TriageState:
    if state.get("refused"):
        _emit(sink, {"phase": "checker", "result": "skipped_due_to_refusal"})
        return state
    res = checker_mod.check_draft(state["draft"], state["subgraph"], state["tenant_id"])
    _emit(sink, {"phase": "checker", "result": {"passed": res.passed, "issues": res.issues}})
    return state


def run_triage(tenant_id: str, finding_id: str, sink: Callable[[Dict[str, Any]], None]) -> TriageState:
    # Provide demo metrics labeled as simulated
    metrics = {"prefix_tokens": 1200, "suffix_tokens": 300, "cached_tokens": 1100, "cache_hit_ratio": 0.9, "input_cost_usd": 0.0025}
    metrics["prompt_tokens"] = metrics["prefix_tokens"] + metrics["suffix_tokens"]
    metrics["usd_estimate"] = metrics["input_cost_usd"]
    metrics["demo_simulated_metrics"] = True
    _emit(sink, {"phase": "metrics", "metrics": metrics})

    initial: TriageState = {"tenant_id": tenant_id, "finding_id": finding_id, "steps": [], "metrics": metrics}

    if _HAS_LANGGRAPH:
        sg = StateGraph(TriageState)
        sg.add_node("planner", lambda s: _planner(s, sink))
        sg.add_node("operator", lambda s: _operator(s, sink))
        sg.add_node("checker", lambda s: _checker(s, sink))
        sg.add_edge(START, "planner")
        sg.add_edge("planner", "operator")
        sg.add_edge("operator", "checker")
        sg.add_edge("checker", END)
        app = sg.compile()
        final: TriageState = app.invoke(initial)  # synchronous path is fine for this demo
        return final
    else:
        # Fallback sequential execution (should not be used if langgraph is installed)
        st = _planner(initial, sink)
        st = _operator(st, sink)
        st = _checker(st, sink)
        return st
