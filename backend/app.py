from __future__ import annotations
import asyncio
import os
import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from agent import graph as graph_mod
from agent import scope as scope_mod
from agent import runner as runner_mod
from agent import checker as checker_mod
from agent import security_sources as sec_mod
from agent import retrieval as retrieval_mod
from agent.cases import finding_context
from agent.delivery import deliver
from agent.promotion import request_promotion
from agent.scoring import load_scoring
from .otel_stub import init_otel
from types import SimpleNamespace
import json
from pathlib import Path

init_otel()
app = FastAPI(title="ThreatAI Security Analyst Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION = SimpleNamespace(tenant_id=os.environ.get("DEMO_TENANT", "tenant_demo_acme"), actor="analyst:demo-1")
# Try to load the seed graph once at startup (best-effort)
try:
    seed_path = os.path.join(os.path.dirname(__file__), "..", "data", "seed_graph.json")
    graph_mod.load_seed(seed_path)
except Exception:
    pass
# Merge ingested scanner findings (Gitleaks, TruffleHog, Trivy, Semgrep, Prowler) if any were ingested
SECURITY_DB = os.environ.get("SECURITY_DB", str(sec_mod.DEFAULT_DB))
try:
    if os.environ.get("SECURITY_AUTOLOAD_FIXTURES") == "1" and not sec_mod.load(SECURITY_DB, SESSION.tenant_id):
        _fx, _ = sec_mod.collect("fixtures", SESSION.tenant_id)
        sec_mod.store(_fx, SECURITY_DB)
    if sec_mod.merge_into_graph(graph_mod._ACTIVE_GRAPH, sec_mod.load(SECURITY_DB)):
        graph_mod.persist_to_sqlite(Path("backend/var/graph.db"))
except Exception:
    pass


def _factors_for(n):
    """Readable factors from the seeded gold labels. Empty when the node has none."""
    gf = (n.props.get("gold_factors") if n else None) or {}
    if isinstance(gf, dict) and gf:
        return [{"name": str(k).replace("_", " "), "value": str(v)} for k, v in gf.items()]
    return []


def _risk_for(n):
    band = (n.props.get("gold_band") if n else "medium") if n else "medium"
    score = {"critical": 0.95, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.05}.get(band, 0.5)
    return {"band": band, "score": score, "factors": _factors_for(n)}


def _draft_for(n, evidence_ids, finding_id, band, subgraph=None):
    """Reply text comes from the model. Citations are limited to the graph."""
    from agent import reply as reply_mod
    sub = subgraph or {"nodes": [{"id": c} for c in evidence_ids], "edges": []}
    nodes = [{"id": node.get("id"), "type": node.get("type"), "label": node.get("label")} for node in sub.get("nodes", [])]
    edges = [{"src": edge.get("src"), "type": edge.get("type"), "dst": edge.get("dst")} for edge in sub.get("edges", [])]
    draft, _metrics = reply_mod.draft_case(
        finding_id=finding_id,
        title=(n.props.get("title") if n else "") or finding_id,
        ask=(n.props.get("ask") if n else "") or "",
        band=band,
        nodes=nodes,
        edges=edges,
        evidence_ids=evidence_ids,
        owner_id=(n.props.get("owner_id") if n else None) or "owner:team-facilities",
    )
    return draft

# In-memory run queues for SSE
RUN_QUEUES: Dict[str, asyncio.Queue] = {}
RUN_RESULTS: Dict[str, Dict[str, Any]] = {}
RUN_TASKS: Dict[str, asyncio.Task] = {}
RUN_HISTORY: Dict[str, list] = {}
RUN_SEQ: Dict[str, int] = {}

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/session")
async def get_session():
    return {"tenant_id": SESSION.tenant_id, "actor": SESSION.actor}


@app.get("/api/findings")
async def list_findings(status: str = "open", limit: int = 50):
    tenant_id = SESSION.tenant_id
    g = graph_mod._ACTIVE_GRAPH
    if not g:
        raise HTTPException(500, "Graph not loaded")
    rows = []
    for n in g._nodes.values():
        if n.type == "finding" and n.tenant_id == tenant_id:
            asset_ids = n.props.get("asset_ids", [])
            asset = g.get(asset_ids[0]) if asset_ids else None
            rows.append({
                "finding_id": n.id.split(":", 1)[1],
                "node_id": n.id,
                "title": n.props.get("title", n.label),
                "ask": n.props.get("ask"),
                "severity": n.props.get("severity", "medium"),
                "status": n.props.get("status", "open"),
                "asset_ids": asset_ids,
                "asset_label": asset.label if asset else None,
                "updated_at": n.props.get("updated_at", datetime.utcnow().isoformat()+"Z"),
                "source_tool": n.props.get("source_tool"),
            })
    return {"findings": rows[:limit]}


@app.get("/api/findings/{finding_id}")
async def get_finding(finding_id: str):
    tenant_id = SESSION.tenant_id
    node_id = f"finding:{finding_id}"
    n = graph_mod._ACTIVE_GRAPH.get(node_id) if graph_mod._ACTIVE_GRAPH else None
    if not n:
        raise HTTPException(404, "not found")
    v = scope_mod.guard(SESSION, "get_finding", {"tenant_id": tenant_id, "finding_id": finding_id}, run_id=str(uuid.uuid4()))
    if not v.allowed:
        return JSONResponse(status_code=403, content=v.__dict__)
    evidence = [{"kind": "http", "summary": n.props.get("title", n.label)}]
    asset_ids = n.props.get("asset_ids", [])
    asset = graph_mod._ACTIVE_GRAPH.get(asset_ids[0]) if asset_ids and graph_mod._ACTIVE_GRAPH else None
    out = {"finding_id": finding_id, "node_id": node_id, "title": n.props.get("title", n.label), "ask": n.props.get("ask"), "theme": n.props.get("theme", "request"), "severity": n.props.get("severity", "medium"), "status": n.props.get("status", "open"), "asset_ids": asset_ids, "asset_label": asset.label if asset else None, "evidence": evidence, "prior_remediation": None}
    ctx = finding_context(finding_id)
    out["audience"] = ctx["audience"]
    out["pipeline"] = ctx["pipeline"]
    if n.props.get("source_tool"):
        # Scanner finding: location and redacted preview only, never a raw secret
        out["evidence"] = [{"kind": n.props.get("category", "code"), "summary": n.props.get("title", n.label)}]
        for k in ("source_tool", "rule_id", "category", "file", "line", "fingerprint", "masked_preview", "references", "synthetic"):
            out[k] = n.props.get(k)
    return {"finding": out}


@app.post("/api/graph/enrich")
async def enrich_asset_graph(payload: Dict[str, Any]):
    tenant_id = payload.get("tenant_id")
    finding_id = payload.get("finding_id")
    k_hops = int(payload.get("k_hops", 2))
    question = payload.get("question")
    v = scope_mod.guard(SESSION, "enrich_asset_graph", {"tenant_id": tenant_id, "finding_id": finding_id, "requested_action": question or ""}, run_id=str(uuid.uuid4()))
    if not v.allowed:
        return JSONResponse(status_code=403, content=v.__dict__)
    sub = retrieval_mod.retrieve(tenant_id, finding_id, k=k_hops, question=question)
    return {"subgraph": sub}


@app.post("/api/rank_risk")
async def rank_risk(payload: Dict[str, Any]):
    tenant_id = payload.get("tenant_id")
    finding_id = payload.get("finding_id")
    sub_nodes = payload.get("subgraph_node_ids", [])
    v = scope_mod.guard(SESSION, "rank_risk", {"tenant_id": tenant_id, "finding_id": finding_id, "subgraph_node_ids": sub_nodes}, run_id=str(uuid.uuid4()))
    if not v.allowed:
        return JSONResponse(status_code=403, content=v.__dict__)
    n = graph_mod._ACTIVE_GRAPH.get(f"finding:{finding_id}") if graph_mod._ACTIVE_GRAPH else None
    band = (n.props.get("gold_band") if n else "medium") if n else "medium"
    risk = {"band": band, "score": {"critical": 0.95, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.05}.get(band, 0.5), "factors": [{"name": "exposure", "weight": 0.5, "value": n.props.get("exposure", "dmz_mgmt_ui") if n else "", "evidence_ids": sub_nodes[:2]}]}
    return {"risk": risk}


@app.post("/api/draft_remediation")
async def draft_remediation(payload: Dict[str, Any]):
    tenant_id = payload.get("tenant_id")
    finding_id = payload.get("finding_id")
    risk_band = payload.get("risk_band")
    evidence_ids = payload.get("evidence_ids", [])
    v = scope_mod.guard(SESSION, "draft_remediation", {"tenant_id": tenant_id, "finding_id": finding_id, "evidence_ids": evidence_ids, "requested_action": "draft remediation"}, run_id=str(uuid.uuid4()))
    if not v.allowed:
        return JSONResponse(status_code=403, content=v.__dict__)
    n = graph_mod._ACTIVE_GRAPH.get(f"finding:{finding_id}") if graph_mod._ACTIVE_GRAPH else None
    draft = _draft_for(n, evidence_ids[:2] or [f"finding:{finding_id}"], finding_id, risk_band)
    return {"draft": draft}


@app.post("/api/check_scope")
async def check_scope(payload: Dict[str, Any]):
    action = payload.get("requested_action", "")
    verdict = scope_mod.check_scope(payload.get("tenant_id"), action, payload.get("target_ids", []))
    if "shut the model down" in action.lower():
        state = load_scoring(str(Path(__file__).resolve().parents[1] / "data" / "scoring_state.json"))
        after, reason = request_promotion(state, SESSION.actor)
        verdict = {**verdict, "allowed": False, "reason": reason, "live_model": after.live_model}
    return {"verdict": verdict}


@app.post("/api/decisions")
async def record_decision(payload: Dict[str, Any]):
    tenant_id = payload.get("tenant_id")
    run_id = payload.get("run_id")
    finding_id = payload.get("finding_id")
    decision = str(payload.get("decision", "")).lower()
    actor = payload.get("actor")
    note = payload.get("note", "")
    # Enforce run gating for Approve: must reference a completed, checker-passed run for this tenant/finding
    if decision == "approve":
        if not run_id or run_id not in RUN_HISTORY or run_id not in RUN_RESULTS:
            return JSONResponse(status_code=403, content={"allowed": False, "reason": "requires_completed_run", "detail": "Missing or unknown run_id"})
        hist = RUN_HISTORY.get(run_id) or []
        has_checker_pass = any((ev.get("phase") == "checker" and ev.get("result", {}).get("passed") is True) for ev in hist if isinstance(ev, dict))
        final = RUN_RESULTS.get(run_id) or {}
        is_final = bool(final)
        if not (has_checker_pass and is_final):
            return JSONResponse(status_code=403, content={"allowed": False, "reason": "checker_not_passed_or_incomplete"})
        if str(final.get("finding_id")) != str(finding_id):
            return JSONResponse(status_code=403, content={"allowed": False, "reason": "finding_mismatch"})
        if str(final.get("tenant_id")) != str(SESSION.tenant_id):
            return JSONResponse(status_code=403, content={"allowed": False, "reason": "cross_tenant"})
    audience = finding_context(str(finding_id))["audience"] if finding_id else "Credit risk"
    item = deliver(decision, audience, bool(run_id and run_id in RUN_RESULTS))
    note = item.note
    # Scope guard (tenant, actor, destructive notes, cross-tenant references)
    v = scope_mod.guard(SESSION, "record_decision", {"tenant_id": tenant_id, "run_id": run_id, "finding_id": finding_id, "decision": decision, "actor": actor, "note": note}, run_id=run_id)
    if not v.allowed:
        return JSONResponse(status_code=403, content=v.__dict__)
    import sqlite3
    scope_mod._ensure_db()
    con = sqlite3.connect(scope_mod._AUDIT_DB_PATH)
    cur = con.cursor()
    decision_id = str(uuid.uuid4())
    ts = datetime.utcnow().isoformat()+"Z"
    cur.execute(
        "INSERT INTO decisions (decision_id, run_id, tenant_id, finding_id, decision, actor, note, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (decision_id, run_id, tenant_id, finding_id, decision.title(), actor, note, ts),
    )
    con.commit()
    con.close()
    return {"record": {"decision_id": decision_id, "run_id": run_id, "tenant_id": tenant_id, "finding_id": finding_id, "decision": decision.title(), "actor": actor, "ts": ts}, "delivery": {"queue": item.queue, "sent": item.sent, "note": item.note}}


@app.post("/api/runs")
async def start_run(payload: Dict[str, Any] = Body(...)):
    tenant_id = SESSION.tenant_id
    finding_id = str(payload.get("finding_id"))
    if not finding_id:
        raise HTTPException(400, "finding_id required")
    run_id = str(uuid.uuid4())
    q: asyncio.Queue = asyncio.Queue()
    RUN_QUEUES[run_id] = q
    RUN_HISTORY[run_id] = []
    RUN_SEQ[run_id] = 0

    async def _sink(evt: Dict[str, Any]):
        # Enqueue immediately in event-loop order so steps arrive before final
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(q.put_nowait, {"event": "step", "data": json.dumps(evt)})
        except RuntimeError:
            # Fallback when no running loop found
            await q.put({"event": "step", "data": json.dumps(evt)})

    async def _run():
        try:
            # Stream deterministic steps synchronously to guarantee ordering before final
            def _record(ev: Dict[str, Any]) -> Dict[str, Any]:
                # Persist per-run history with monotonically increasing sequence
                RUN_SEQ[run_id] += 1
                ev = {**ev, "seq": RUN_SEQ[run_id]}
                RUN_HISTORY[run_id].append(ev)
                return ev
            loop = asyncio.get_running_loop()

            def _sink(evt: Dict[str, Any]) -> None:
                recorded = _record(evt)
                loop.call_soon_threadsafe(q.put_nowait, {"data": json.dumps(recorded)})

            state = await asyncio.to_thread(runner_mod.run_triage, tenant_id, finding_id, _sink)
            final = {
                "tenant_id": tenant_id,
                "finding_id": finding_id,
                "subgraph": state.get("subgraph"),
                "risk": state.get("risk"),
                "draft": state.get("draft"),
                "steps": state.get("steps") or [],
                "metrics": state.get("metrics"),
                "refused": state.get("refused"),
                "refusal_reason": state.get("refusal_reason"),
            }
            RUN_RESULTS[run_id] = final
            await q.put({"data": json.dumps(_record({"final": True, **final}))})
        except Exception as e:
            # Persist error details to artifacts and emit an error event
            try:
                from pathlib import Path
                Path("/opt/cursor/artifacts").mkdir(parents=True, exist_ok=True)
                (Path(f"/opt/cursor/artifacts/sse_run_error_{run_id}.log")).write_text(repr(e))
            except Exception:
                pass
            await q.put({"data": json.dumps({"error": True, "message": repr(e)})})
        finally:
            await q.put({"data": json.dumps({"event": "done"})})

    # Launch run in background; history captures phases for any subscriber (early or delayed)
    RUN_TASKS[run_id] = asyncio.create_task(_run())
    return {"run_id": run_id}


@app.get("/runs/{run_id}/events")
async def stream_events(run_id: str):
    q = RUN_QUEUES.get(run_id)
    if q is None:
        raise HTTPException(404, "run not found")

    async def event_generator():
        # Determine subscription point; only replay events recorded up to this seq
        starting_seq = RUN_SEQ.get(run_id, 0) or 0
        last_sent_seq = 0
        # Replay bounded by starting_seq
        for ev in RUN_HISTORY.get(run_id, []):
            seq = int(ev.get("seq", 0) or 0)
            if seq <= starting_seq:
                data = {**ev, "replayed": True}
                yield {"data": json.dumps(data)}
                last_sent_seq = max(last_sent_seq, seq)
        while True:
            evt = await q.get()
            data = evt.get("data") if isinstance(evt, dict) else None
            if not data:
                continue
            try:
                obj = json.loads(data)
            except Exception:
                obj = None
            if isinstance(obj, dict) and obj.get("event") == "done":
                yield {"data": data}
                break
            # De-duplicate: skip any queued events at or before last_sent_seq
            if isinstance(obj, dict):
                seq = int(obj.get("seq", 0) or 0)
                if seq and seq <= last_sent_seq:
                    continue
                if seq:
                    last_sent_seq = max(last_sent_seq, seq)
            # Emit as default 'message' event with data only
            yield {"data": data}
    return EventSourceResponse(event_generator())

@app.get("/runs/{run_id}/history")
async def get_history(run_id: str):
    return {"history": RUN_HISTORY.get(run_id, []), "seq": RUN_SEQ.get(run_id, 0)}


@app.get("/api/audit")
async def list_audit(limit: int = 20):
    # Read from SQLite audit log
    import sqlite3
    scope_mod._ensure_db()
    con = sqlite3.connect(scope_mod._AUDIT_DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT audit_id, run_id, tenant_id, requested_tenant_id, finding_id, tool, decision, reason, matched_rule, ts FROM audit_log ORDER BY ts DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    cols = ["audit_id", "run_id", "tenant_id", "requested_tenant_id", "finding_id", "tool", "decision", "reason", "matched_rule", "ts"]
    return {"audit": [dict(zip(cols, r)) for r in rows]}

@app.post("/api/run_simulate")
async def run_simulate(payload: Dict[str, Any] = Body(...)):
    tenant_id = SESSION.tenant_id
    finding_id = str(payload.get("finding_id"))
    history = []
    def rec(ev: Dict[str, Any]):
        ev = {**ev, "seq": len(history) + 1}
        history.append(ev)
    state = runner_mod.run_triage(tenant_id, finding_id, rec)
    final = {
        "tenant_id": tenant_id,
        "finding_id": finding_id,
        "subgraph": state.get("subgraph"),
        "risk": state.get("risk"),
        "draft": state.get("draft"),
        "steps": state.get("steps") or [],
        "metrics": state.get("metrics"),
    }
    rec({"final": True, **final})
    return {"history": history, "final": final}

@app.post("/api/security/ingest")
async def security_ingest(payload: Dict[str, Any] = Body(default={})):
    """Load scanner reports (reports/security/*.json) or the synthetic fixtures into SQLite
    and the GraphRAG graph. Reads fixed project folders only; no paths from the request."""
    source = str((payload or {}).get("source", "auto"))
    if source not in ("auto", "reports", "fixtures"):
        raise HTTPException(400, "source must be auto, reports or fixtures")
    tenant_id = SESSION.tenant_id
    findings, files = sec_mod.collect(source, tenant_id)
    sec_mod.store(findings, SECURITY_DB, replace_tenant=tenant_id)
    sec_mod.remove_from_graph(graph_mod._ACTIVE_GRAPH)
    sec_mod.merge_into_graph(graph_mod._ACTIVE_GRAPH, sec_mod.load(SECURITY_DB))
    try:
        graph_mod.persist_to_sqlite(Path("backend/var/graph.db"))
    except Exception:
        pass
    scope_mod._write_audit(None, tenant_id, None, None, "security_ingest", "allow", "in_scope", None)
    return {"ingested": len(findings), "files": [Path(f).name for f in files], "summary": sec_mod.summary(findings)}


@app.get("/api/security/summary")
async def security_summary():
    rows = sec_mod.load(SECURITY_DB, SESSION.tenant_id)
    return {"tenant_id": SESSION.tenant_id, "total": len(rows), "by_tool": sec_mod.summary(rows)}
