# Optional LightRAG retrieval backend

ThreatAI retrieves context from its SQLite GraphRAG graph. [LightRAG](https://github.com/HKUDS/LightRAG)
(package `lightrag-hku`, pinned 1.5.7) can be switched on next to it. It is **off by default**,
so the normal demo, tests and evals do not change.

## What it does

* Indexes, per tenant, one text document for every graph node of that tenant (camera findings,
  assets, segments, owners, weaknesses, scanner findings from Gitleaks, TruffleHog, Trivy,
  Semgrep and Prowler, and the tool nodes) plus the synthetic runbooks in `data/runbooks/`.
* Answers the agent's retrieval query for a finding and attaches the answer to the subgraph as
  `lightrag_context` (with `retrieval_backend: "lightrag"`).
* Node ids, citations and the checker still come from the graph, so LightRAG can add context
  but never an id the checker would accept without it existing in the tenant's graph.
* Each tenant has its own working directory (`backend/var/lightrag/<tenant>`); a query only sees
  that tenant's documents. A foreign finding returns an empty subgraph before LightRAG is called.
* If LightRAG or Ollama fails, retrieval falls back to SQLite and records `lightrag_error`.
* Scanner findings are redacted at ingest, so no secret value is ever indexed.

## Enable it

LLM and embeddings come from Ollama. Nothing calls a paid API. OmniRoute is not involved.

| Env | Default |
|---|---|
| `RETRIEVAL_BACKEND` | `sqlite` (set `lightrag` to enable) |
| `OLLAMA_HOST` | `http://192.168.70.20:11434` |
| `LIGHTRAG_LLM_MODEL` | `qwen3:4b` |
| `LIGHTRAG_EMBED_MODEL` | `nomic-embed-text` |
| `LIGHTRAG_EMBED_DIM` | `768` (must match the embedding model) |
| `LIGHTRAG_QUERY_MODE` | `hybrid` (`naive`, `local`, `global`, `hybrid`, `mix`) |
| `LIGHTRAG_WORKDIR` | `backend/var/lightrag` |

Local run:

    ollama pull qwen3:4b && ollama pull nomic-embed-text     # on the Ollama host
    make lightrag-deps
    make lightrag-index
    RETRIEVAL_BACKEND=lightrag uvicorn backend.app:app --port 54123

Docker:

    docker compose --profile lightrag up --build backend-lightrag   # API on :54124

Query from the CLI:

    python3 -m agent.lightrag_backend query F-101 "who owns this asset?"

## Tests

* `make test-lightrag` uses a mocked LightRAG client (no network).
* `make lightrag-smoke` runs the real `lightrag-hku` library end to end with a fake LLM and fake
  embeddings, offline.

## Notes

* Indexing calls the LLM once per document for entity extraction; with a small local model the
  first index takes a few minutes. Later queries reuse the index while the graph is unchanged.
* In LightRAG mode the run waits for the LightRAG answer before streaming the operator step, so
  a slow Ollama makes runs slower. Keep the default SQLite backend for the live demo unless
  Ollama is warm.
