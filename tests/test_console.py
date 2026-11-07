"""The desk console names the frameworks that actually ran."""
from agent.console import describe
from agent.runner import _emit


def test_lines_name_langgraph_langchain_and_graphrag():
    planner = describe({"phase": "planner", "verdict": {"allowed": True, "reason": "in_scope"}})
    graph = describe({"phase": "operator", "tool": "enrich_asset_graph", "result": {
        "subgraph_nodes": 11, "subgraph_edges": 8, "retrieval": "SQLite GraphRAG",
    }})
    draft = describe({"phase": "operator", "tool": "draft_remediation", "result": {
        "cited_count": 2, "model": "gpt-5.6-terra",
    }})
    assert "LangGraph planner" in planner
    assert "SQLite GraphRAG returned 11 nodes and 8 edges." == graph
    assert "LangChain Core" in draft
    assert "gpt-5.6-terra" in draft


def test_lightrag_line_names_lightrag():
    line = describe({"phase": "operator", "tool": "enrich_asset_graph", "result": {
        "subgraph_nodes": 4, "subgraph_edges": 3, "retrieval": "LightRAG",
    }})
    assert line.startswith("LightRAG returned 4 nodes")


def test_emit_attaches_the_line():
    seen = []
    _emit(seen.append, {"phase": "checker", "result": {"passed": True, "issues": []}})
    assert seen[0]["line"] == "LangGraph checker passed the draft."
