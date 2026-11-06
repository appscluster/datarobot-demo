#!/usr/bin/env python3
"""Smoke test for the optional LightRAG backend with a FAKE LLM and FAKE embeddings.

Runs the real lightrag-hku library end to end (index + naive query) without Ollama
or any external API. Usage: python3 scripts/lightrag_smoke.py
"""
import asyncio
import hashlib
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lightrag import LightRAG  # noqa: E402
from lightrag.utils import EmbeddingFunc  # noqa: E402

from agent import graph as graph_mod  # noqa: E402
from agent import lightrag_backend as lr  # noqa: E402
from agent import security_sources as sec  # noqa: E402

DIM = 64
SEEN_PROMPTS = []


async def fake_embed(texts, **_):
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        v = np.frombuffer((h * (DIM // len(h) + 1))[:DIM], dtype=np.uint8).astype(np.float32)
        out.append(v / (np.linalg.norm(v) or 1.0))
    return np.array(out)


async def fake_llm(prompt, system_prompt=None, history_messages=None, **kwargs):
    SEEN_PROMPTS.append((system_prompt or "") + prompt)
    if kwargs.get("keyword_extraction"):
        return '{"high_level_keywords": ["finding"], "low_level_keywords": ["F-101", "camera"]}'
    ctx = (system_prompt or "") + prompt
    if "F-101" in ctx:
        return "FAKE-LLM: F-101 is on asset cam-01 owned by Facilities; see RB-CAM-DEFAULT-CRED."
    return "FAKE-LLM: no context"


def factory(tenant, cfg):
    wd = Path(cfg["workdir"]) / tenant
    wd.mkdir(parents=True, exist_ok=True)
    return LightRAG(working_dir=str(wd), llm_model_func=fake_llm, llm_model_name="fake",
                    embedding_func=EmbeddingFunc(embedding_dim=DIM, max_token_size=8192, func=fake_embed))


def main() -> int:
    g = graph_mod.load_seed(ROOT / "data" / "seed_graph.json")
    fs, _ = sec.collect("fixtures", "tenant_demo_acme")
    sec.merge_into_graph(g, fs)
    with tempfile.TemporaryDirectory() as td:
        r = lr.LightRAGRetriever(rag_factory=factory, cfg={**lr.settings(), "workdir": td, "mode": "naive"})
        n = r.index("tenant_demo_acme", g)
        out = r.query("tenant_demo_acme", "F-101", "Who owns the asset for F-101?")
        files = sorted(p.name for p in (Path(td) / "tenant_demo_acme").iterdir())
    print(f"indexed documents: {n}")
    print(f"lightrag storage files: {files}")
    print(f"answer: {out['answer']}")
    ok = n > 0 and "F-101" in out["answer"] and any("F-101" in p for p in SEEN_PROMPTS)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
