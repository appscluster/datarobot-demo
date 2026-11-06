"""Retrieval dispatch for the agent.

RETRIEVAL_BACKEND=sqlite (default) uses the SQLite GraphRAG graph exactly as before.
RETRIEVAL_BACKEND=lightrag adds a LightRAG answer as extra context on top of the same
tenant scoped subgraph. Node ids, and therefore citations and the checker, always come
from the graph, so LightRAG can enrich the context but never invent a citable id.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from . import graph as graph_mod

_EMPTY = {"nodes": [], "edges": []}


def backend_name() -> str:
    return os.environ.get("RETRIEVAL_BACKEND", "sqlite").strip().lower() or "sqlite"


def retrieve(tenant_id: str, finding_id: str, k: int = 2, question: Optional[str] = None) -> Dict[str, Any]:
    g = graph_mod._ACTIVE_GRAPH
    sub = g.retrieve(tenant_id, finding_id, k=k, question=question) if g else dict(_EMPTY)
    if backend_name() != "lightrag" or not sub.get("nodes"):
        return sub
    try:
        from . import lightrag_backend
        extra = lightrag_backend.get_retriever().query(tenant_id, finding_id, question)
    except Exception as e:  # LightRAG is optional; never break the demo
        sub = dict(sub)
        sub["retrieval_backend"] = "sqlite"
        sub["lightrag_error"] = type(e).__name__
        return sub
    sub = dict(sub)
    sub["retrieval_backend"] = "lightrag"
    sub["lightrag_context"] = extra.get("answer", "")
    sub["lightrag_mode"] = extra.get("mode")
    return sub
