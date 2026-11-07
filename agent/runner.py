from __future__ import annotations
from typing import Any, Dict, List, TypedDict, Callable
import time

from . import graph as graph_mod
from . import checker as checker_mod
from . import scope as scope_mod
from . import retrieval as retrieval_mod
from . import reply as reply_mod
from .cases import finding_context
from .console import describe
from .reply import for_draft

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
        if not event.get("line"):
            event = {**event, "line": describe(event)}
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
    sub = retrieval_mod.retrieve(tenant_id, finding_id, k=3, question=None)
    retrieval = "LightRAG" if sub.get("retrieval_backend") == "lightrag" else "SQLite GraphRAG"
    _emit(sink, {"phase": "operator", "tool": "enrich_asset_graph", "result": {
        "subgraph_nodes": len(sub.get("nodes", [])),
        "subgraph_edges": len(sub.get("edges", [])),
        "retrieval": retrieval,
    }})
    state["subgraph"] = sub
    # Rank risk (simple heuristic from node props)
    n = graph_mod._ACTIVE_GRAPH.get(f"finding:{finding_id}") if graph_mod._ACTIVE_GRAPH else None
    band = (n.props.get("gold_band") if n else "medium") if n else "medium"
    gf = (n.props.get("gold_factors") if n else None) or {}
    factors = [{"name": str(k).replace("_", " "), "value": str(v)} for k, v in gf.items()] if isinstance(gf, dict) else []
    risk = {"band": band, "score": {"critical": 0.95, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.05}.get(band, 0.5), "factors": factors}
    state["risk"] = risk
    _emit(sink, {"phase": "operator", "tool": "rank_risk", "result": risk})
    nodes = [{"id": node.get("id"), "type": node.get("type"), "label": node.get("label")} for node in sub.get("nodes", [])]
    edges = [{"src": edge.get("src"), "type": edge.get("type"), "dst": edge.get("dst")} for edge in sub.get("edges", [])]
    nodes, edges = for_draft(nodes, edges, finding_id)
    anchor = f"finding:{finding_id}"
    evidence_ids = [anchor] + [node["id"] for node in nodes if node.get("id") and node.get("id") != anchor][:2]
    ctx = finding_context(finding_id)
    draft, metrics = reply_mod.draft_case(
        finding_id=finding_id,
        title=(n.props.get("title") if n else "") or finding_id,
        ask=(n.props.get("ask") if n else "") or "",
        band=band,
        nodes=nodes,
        edges=edges,
        evidence_ids=evidence_ids,
        owner_id=(n.props.get("owner_id") if n else None) or "owner:team-facilities",
        decision=ctx["pipeline"]["summary"],
    )
    state["draft"] = draft
    state["metrics"] = metrics
    _emit(sink, {"phase": "operator", "tool": "draft_remediation", "result": {"cited_count": len(draft.get("cited_ids") or []), "model": draft.get("model")}})
    _emit(sink, {"phase": "metrics", "metrics": metrics})
    return state


def _record_monitoring(state: TriageState, checker_passed: bool) -> Dict[str, Any]:
    from agent.monitoring import record_run
    draft = state.get("draft") or {}
    steps = draft.get("steps") if isinstance(draft, dict) else []
    completion = " ".join(str(step.get("text") or "") for step in (steps or []) if isinstance(step, dict))
    metrics = state.get("metrics") or {}
    return record_run(
        finding_id=str(state.get("finding_id") or ""),
        tenant_id=str(state.get("tenant_id") or ""),
        model=str(metrics.get("model") or ""),
        prompt_tokens=int(metrics.get("prompt_tokens") or 0),
        completion_tokens=int(metrics.get("completion_tokens") or 0),
        completion=completion,
        checker_passed=checker_passed,
    )


def _checker(state: TriageState, sink: Callable[[Dict[str, Any]], None]) -> TriageState:
    if state.get("refused"):
        _emit(sink, {"phase": "checker", "result": "skipped_due_to_refusal"})
        _emit(sink, {"phase": "monitoring", "result": _record_monitoring(state, False)})
        return state
    res = checker_mod.check_draft(state["draft"], state["subgraph"], state["tenant_id"])
    _emit(sink, {"phase": "checker", "result": {"passed": res.passed, "issues": res.issues}})
    _emit(sink, {"phase": "monitoring", "result": _record_monitoring(state, res.passed)})
    return state


def run_triage(tenant_id: str, finding_id: str, sink: Callable[[Dict[str, Any]], None]) -> TriageState:
    initial: TriageState = {"tenant_id": tenant_id, "finding_id": finding_id, "steps": []}

    _emit(sink, {"phase": "graph", "tool": "langgraph"})
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
