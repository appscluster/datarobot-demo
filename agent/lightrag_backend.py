"""Optional LightRAG retrieval backend (HKUDS/LightRAG, package lightrag-hku).

Off by default. Enable with RETRIEVAL_BACKEND=lightrag. LLM and embeddings come from
Ollama only (no paid API):

  OLLAMA_HOST            default http://192.168.70.20:11434
  LIGHTRAG_LLM_MODEL     default qwen3:4b
  LIGHTRAG_EMBED_MODEL   default nomic-embed-text
  LIGHTRAG_EMBED_DIM     default 768
  LIGHTRAG_WORKDIR       default backend/var/lightrag (one sub folder per tenant)
  LIGHTRAG_QUERY_MODE    default hybrid (naive | local | global | hybrid | mix)

Index:  python3 -m agent.lightrag_backend index [--tenant tenant_demo_acme]
Query:  python3 -m agent.lightrag_backend query F-101 "who owns this asset?"

Each tenant gets its own LightRAG working directory and only that tenant's nodes are
indexed, so a query can never read another tenant's documents.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import graph as graph_mod

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_DIR = ROOT / "data" / "runbooks"
_TENANT_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def settings() -> Dict[str, Any]:
    return {
        "ollama_host": os.environ.get("OLLAMA_HOST", "http://192.168.70.20:11434"),
        "llm_model": os.environ.get("LIGHTRAG_LLM_MODEL", "qwen3:4b"),
        "embed_model": os.environ.get("LIGHTRAG_EMBED_MODEL", "nomic-embed-text"),
        "embed_dim": int(os.environ.get("LIGHTRAG_EMBED_DIM", "768")),
        "workdir": os.environ.get("LIGHTRAG_WORKDIR", "backend/var/lightrag"),
        "mode": os.environ.get("LIGHTRAG_QUERY_MODE", "hybrid"),
    }


# ------------------------------------------------------------ documents

def _node_doc(n: Any, neighbours: List[str]) -> str:
    lines = [f"[{n.id}] {n.type}: {n.label}"]
    p = n.props or {}
    for key in ("title", "severity", "status", "source_tool", "rule_id", "category", "file", "line", "remediation"):
        if p.get(key) not in (None, "", []):
            lines.append(f"{key}: {p[key]}")
    if neighbours:
        lines.append("related: " + ", ".join(neighbours))
    return "\n".join(lines)


def build_documents(graph: Any, tenant_id: str, runbook_dir: Path = RUNBOOK_DIR) -> List[Dict[str, str]]:
    """Tenant scoped text documents: one per node (findings, assets, owners, segments,
    weaknesses, tools, scanner findings) plus the synthetic runbooks. Raw secrets never
    exist in the graph (scanner findings are redacted at ingest), so none are indexed."""
    docs: List[Dict[str, str]] = []
    if graph is not None:
        for n in graph._nodes.values():
            if n.tenant_id != tenant_id:
                continue
            nb = sorted({f"{e.type} {e.dst}" for e in graph._adj.get(n.id, [])
                         if graph.tenant_of(e.dst) == tenant_id})
            docs.append({"id": f"node::{n.id}", "text": _node_doc(n, nb), "source": n.id})
    for p in sorted(Path(runbook_dir).glob("RB-*.md")):
        docs.append({"id": f"runbook::{p.stem}", "text": p.read_text(encoding="utf-8"), "source": f"runbook:{p.stem}"})
    return docs


# ------------------------------------------------------------ LightRAG client

def _default_factory(tenant_id: str, cfg: Dict[str, Any]):
    """Build a real LightRAG instance wired to Ollama. Imported lazily so the
    default demo never needs lightrag-hku installed."""
    from functools import partial
    from lightrag import LightRAG
    from lightrag.llm.ollama import ollama_embed, ollama_model_complete
    from lightrag.utils import EmbeddingFunc

    wd = Path(cfg["workdir"]) / _TENANT_SAFE.sub("_", tenant_id)
    wd.mkdir(parents=True, exist_ok=True)
    return LightRAG(
        working_dir=str(wd),
        llm_model_func=ollama_model_complete,
        llm_model_name=cfg["llm_model"],
        llm_model_kwargs={"host": cfg["ollama_host"], "options": {"num_ctx": 8192}, "timeout": 300},
        embedding_func=EmbeddingFunc(
            embedding_dim=cfg["embed_dim"],
            max_token_size=8192,
            func=partial(ollama_embed.func, embed_model=cfg["embed_model"], host=cfg["ollama_host"]),
        ),
    )


def _query_param(mode: str):
    try:
        from lightrag import QueryParam
        try:
            return QueryParam(mode=mode, enable_rerank=False)  # no rerank model in this setup
        except TypeError:
            return QueryParam(mode=mode)
    except Exception:
        return {"mode": mode}


class _LoopThread:
    """A private event loop so sync callers (and async FastAPI handlers) can await LightRAG."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.t = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.t.start()

    def run(self, coro, timeout: float = 120):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)


class LightRAGRetriever:
    def __init__(self, rag_factory: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
                 param_factory: Callable[[str], Any] = _query_param, cfg: Optional[Dict[str, Any]] = None):
        self.cfg = cfg or settings()
        self.rag_factory = rag_factory or _default_factory
        self.param_factory = param_factory
        self._rags: Dict[str, Any] = {}
        self._indexed: Dict[str, str] = {}
        self._loop = _LoopThread()

    async def _rag(self, tenant_id: str):
        if tenant_id not in self._rags:
            rag = self.rag_factory(tenant_id, self.cfg)
            init = getattr(rag, "initialize_storages", None)
            if init:
                await init()
            self._rags[tenant_id] = rag
        return self._rags[tenant_id]

    async def aindex(self, tenant_id: str, graph: Any = None) -> int:
        graph = graph if graph is not None else graph_mod._ACTIVE_GRAPH
        docs = build_documents(graph, tenant_id)
        digest = hashlib.sha256("".join(d["id"] + d["text"] for d in docs).encode()).hexdigest()
        if self._indexed.get(tenant_id) == digest:
            return 0
        rag = await self._rag(tenant_id)
        await rag.ainsert([d["text"] for d in docs], ids=[d["id"] for d in docs],
                          file_paths=[d["source"] for d in docs])
        self._indexed[tenant_id] = digest
        return len(docs)

    async def aquery(self, tenant_id: str, finding_id: str, question: Optional[str] = None) -> Dict[str, Any]:
        await self.aindex(tenant_id)
        rag = await self._rag(tenant_id)
        fid = finding_id if finding_id.startswith("finding:") else f"finding:{finding_id}"
        q = question or f"Summarise the context, owner, exposure and the matching runbook for {fid}."
        q = f"Tenant {tenant_id}. Only use the indexed documents. {q}"
        answer = await rag.aquery(q, param=self.param_factory(self.cfg["mode"]))
        return {"answer": answer if isinstance(answer, str) else str(answer), "mode": self.cfg["mode"]}

    def index(self, tenant_id: str, graph: Any = None) -> int:
        return self._loop.run(self.aindex(tenant_id, graph))

    def query(self, tenant_id: str, finding_id: str, question: Optional[str] = None) -> Dict[str, Any]:
        return self._loop.run(self.aquery(tenant_id, finding_id, question))


_RETRIEVER: Optional[LightRAGRetriever] = None


def get_retriever() -> LightRAGRetriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = LightRAGRetriever()
    return _RETRIEVER


def _main() -> int:
    import argparse
    import json
    import sys
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from agent import security_sources as sec

    ap = argparse.ArgumentParser(description="LightRAG index or query for ThreatAI")
    ap.add_argument("cmd", choices=["index", "query"])
    ap.add_argument("finding_id", nargs="?", default="F-101")
    ap.add_argument("question", nargs="?")
    ap.add_argument("--tenant", default=os.environ.get("DEMO_TENANT", "tenant_demo_acme"))
    a = ap.parse_args()
    g = graph_mod.load_seed(ROOT / "data" / "seed_graph.json")
    sec.merge_into_graph(g, sec.load(os.environ.get("SECURITY_DB", str(sec.DEFAULT_DB))))
    r = get_retriever()
    if a.cmd == "index":
        print(json.dumps({"tenant": a.tenant, "documents": r.index(a.tenant, g), "settings": r.cfg}, indent=2))
    else:
        print(json.dumps(r.query(a.tenant, a.finding_id, a.question), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
