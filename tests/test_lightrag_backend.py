"""Optional LightRAG backend, tested with a mocked LightRAG client (no network, no LLM)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import graph as graph_mod  # noqa: E402
from agent import retrieval  # noqa: E402
from agent import lightrag_backend as lr  # noqa: E402
from agent import security_sources as sec  # noqa: E402

T = "tenant_demo_acme"
OTHER = "tenant_other_corp"


class FakeRag:
    instances = []

    def __init__(self, tenant, cfg):
        self.tenant, self.cfg = tenant, cfg
        self.inserted, self.queries, self.initialized = [], [], False
        FakeRag.instances.append(self)

    async def initialize_storages(self):
        self.initialized = True

    async def ainsert(self, texts, ids=None, file_paths=None):
        self.inserted.append((list(texts), list(ids or []), list(file_paths or [])))

    async def aquery(self, q, param=None):
        self.queries.append((q, param))
        return f"LightRAG context for {self.tenant}: owner Facilities, runbook RB-CAM-DEFAULT-CRED"


@pytest.fixture
def g():
    graph = graph_mod.load_seed(ROOT / "data" / "seed_graph.json")
    fs, _ = sec.collect("fixtures", T)
    sec.merge_into_graph(graph, fs)
    yield graph
    graph_mod.load_seed(ROOT / "data" / "seed_graph.json")


@pytest.fixture
def fake(monkeypatch, tmp_path):
    FakeRag.instances = []
    r = lr.LightRAGRetriever(rag_factory=FakeRag, param_factory=lambda m: {"mode": m},
                             cfg={**lr.settings(), "workdir": str(tmp_path)})
    monkeypatch.setattr(lr, "_RETRIEVER", r)
    return r


def test_default_backend_is_sqlite_and_unchanged(g, monkeypatch):
    monkeypatch.delenv("RETRIEVAL_BACKEND", raising=False)
    assert retrieval.backend_name() == "sqlite"
    assert retrieval.retrieve(T, "F-101", k=2) == g.retrieve(T, "F-101", k=2)


def test_settings_defaults_use_ollama(monkeypatch):
    for k in ("OLLAMA_HOST", "LIGHTRAG_LLM_MODEL", "LIGHTRAG_EMBED_MODEL"):
        monkeypatch.delenv(k, raising=False)
    s = lr.settings()
    assert s["ollama_host"] == "http://192.168.70.20:11434"
    assert s["llm_model"].startswith("qwen3") and s["embed_model"] == "nomic-embed-text"


def test_documents_are_tenant_scoped_and_include_runbooks_and_scanner_findings(g):
    docs = lr.build_documents(g, T)
    srcs = {d["source"] for d in docs}
    assert "finding:F-101" in srcs and "asset:cam-01" in srcs
    assert any(s.startswith("runbook:RB-") for s in srcs)
    assert any(s.startswith("tool:") for s in srcs)
    assert any(s.startswith("finding:F-GL-") for s in srcs)
    assert "finding:F-901" not in srcs and "asset:oc-01" not in srcs
    assert all("tenant_other_corp" not in d["text"] for d in docs)


def test_lightrag_backend_adds_context_but_keeps_graph_ids(g, fake, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_BACKEND", "lightrag")
    base = g.retrieve(T, "F-101", k=2)
    sub = retrieval.retrieve(T, "F-101", k=2)
    assert sub["retrieval_backend"] == "lightrag"
    assert "RB-CAM-DEFAULT-CRED" in sub["lightrag_context"]
    assert sub["nodes"] == base["nodes"] and sub["edges"] == base["edges"]
    rag = FakeRag.instances[0]
    assert rag.tenant == T and rag.initialized
    assert len(rag.inserted) == 1 and "node::finding:F-101" in rag.inserted[0][1]
    assert rag.queries[0][1] == {"mode": "hybrid"}
    # a second query reuses the index (no re-insert when the graph did not change)
    retrieval.retrieve(T, "F-101", k=2)
    assert len(rag.inserted) == 1


def test_lightrag_never_queried_for_foreign_finding(g, fake, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_BACKEND", "lightrag")
    sub = retrieval.retrieve(T, "F-901", k=2)
    assert sub["nodes"] == [] and FakeRag.instances == []


def test_lightrag_failure_falls_back_to_sqlite(g, monkeypatch, tmp_path):
    monkeypatch.setenv("RETRIEVAL_BACKEND", "lightrag")

    def boom(tenant, cfg):
        raise ConnectionError("ollama down")
    monkeypatch.setattr(lr, "_RETRIEVER", lr.LightRAGRetriever(rag_factory=boom, cfg={**lr.settings(), "workdir": str(tmp_path)}))
    sub = retrieval.retrieve(T, "F-101", k=2)
    assert sub["retrieval_backend"] == "sqlite" and sub["lightrag_error"] == "ConnectionError"
    assert sub["nodes"] == g.retrieve(T, "F-101", k=2)["nodes"]
