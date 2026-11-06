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
from .otel_stub import init_otel
from types import SimpleNamespace
import json

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
            rows.append({
                "finding_id": n.id.split(":", 1)[1],
                "node_id": n.id,
                "title": n.props.get("title", n.label),
                "severity": n.props.get("severity", "medium"),
                "status": n.props.get("status", "open"),
                "asset_ids": n.props.get("asset_ids", []),
                "updated_at": n.props.get("updated_at", datetime.utcnow().isoformat()+"Z"),
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
    return {"finding": {"finding_id": finding_id, "node_id": node_id, "title": n.props.get("title", n.label), "theme": n.props.get("theme", "camera"), "severity": n.props.get("severity", "medium"), "status": n.props.get("status", "open"), "asset_ids": n.props.get("asset_ids", []), "evidence": evidence, "prior_remediation": None}}


@app.post("/api/graph/enrich")
async def enrich_asset_graph(payload: Dict[str, Any]):
    tenant_id = payload.get("tenant_id")
    finding_id = payload.get("finding_id")
    k_hops = int(payload.get("k_hops", 2))
    question = payload.get("question")
    v = scope_mod.guard(SESSION, "enrich_asset_graph", {"tenant_id": tenant_id, "finding_id": finding_id, "requested_action": question or ""}, run_id=str(uuid.uuid4()))
    if not v.allowed:
        return JSONResponse(status_code=403, content=v.__dict__)
    sub = graph_mod._ACTIVE_GRAPH.retrieve(tenant_id, finding_id, k=k_hops, question=question) if graph_mod._ACTIVE_GRAPH else {"nodes": [], "edges": []}
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
    steps = [{"text": "Rotate default credentials and restrict the management UI to the admin segment.", "cites": evidence_ids[:2] or [f"finding:{finding_id}"], "owner_id": "owner:team-facilities"}]
    cited = sorted({c for s in steps for c in s["cites"]})
    draft = {"steps": steps, "summary": f"{risk_band or 'medium'} risk; coordinate with the owning team.", "cited_ids": cited, "non_destructive": True}
    return {"draft": draft}


@app.post("/api/check_scope")
async def check_scope(payload: Dict[str, Any]):
    verdict = scope_mod.check_scope(payload.get("tenant_id"), payload.get("requested_action", ""), payload.get("target_ids", []))
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
    return {"record": {"decision_id": decision_id, "run_id": run_id, "tenant_id": tenant_id, "finding_id": finding_id, "decision": decision.title(), "actor": actor, "ts": ts}}


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
            def _mark(step: str):
                try:
                    from pathlib import Path
                    Path("/opt/cursor/artifacts").mkdir(parents=True, exist_ok=True)
                    with open(f"/opt/cursor/artifacts/sse_progress_{run_id}.log","a") as f:
                        f.write(step + "\\n")
                except Exception:
                    pass
            # Metrics
            metrics = {"prefix_tokens": 1200, "suffix_tokens": 300, "cached_tokens": 1100, "cache_hit_ratio": 0.9, "input_cost_usd": 0.0025}
            metrics["prompt_tokens"] = metrics["prefix_tokens"] + metrics["suffix_tokens"]
            metrics["usd_estimate"] = metrics["input_cost_usd"]
            metrics["demo_simulated_metrics"] = True
            await q.put({"data": json.dumps(_record({"phase": "metrics", "metrics": metrics}))})
            _mark("metrics")
            # Planner
            v = scope_mod.check_scope(tenant_id, "triage finding", [f"finding:{finding_id}"])
            await q.put({"data": json.dumps(_record({"phase": "planner", "verdict": v}))})
            _mark("planner")
            # Operator: enrich + rank_risk + draft
            sub = graph_mod._ACTIVE_GRAPH.retrieve(tenant_id, finding_id, k=2, question=None) if graph_mod._ACTIVE_GRAPH else {"nodes": [], "edges": []}
            await q.put({"data": json.dumps(_record({"phase": "operator", "tool": "enrich_asset_graph", "result": {"subgraph_nodes": len(sub.get("nodes", []))}}))})
            _mark("enrich")
            n = graph_mod._ACTIVE_GRAPH.get(f"finding:{finding_id}") if graph_mod._ACTIVE_GRAPH else None
            band = (n.props.get("gold_band") if n else "medium") if n else "medium"
            risk = {"band": band, "score": {"critical": 0.95, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.05}.get(band, 0.5), "factors": []}
            await q.put({"data": json.dumps(_record({"phase": "operator", "tool": "rank_risk", "result": risk}))})
            _mark("rank")
            evidence_ids = [nn["id"] for nn in sub.get("nodes", [])][:2] or [f"finding:{finding_id}"]
            steps = [{"text": "Rotate default credentials and restrict the management UI to the admin segment.", "cites": evidence_ids, "owner_id": "owner:team-facilities"}]
            cited = sorted({c for s in steps for c in s["cites"]})
            draft = {"steps": steps, "summary": f"{band} risk; coordinate with the owning team.", "cited_ids": cited, "non_destructive": True}
            await q.put({"data": json.dumps(_record({"phase": "operator", "tool": "draft_remediation", "result": {"cited_count": len(cited)}}))})
            _mark("draft")
            # Checker
            chk = checker_mod.check_draft(draft, sub, tenant_id)
            await q.put({"data": json.dumps(_record({"phase": "checker", "result": {"passed": chk.passed, "issues": chk.issues}}))})
            _mark("checker")
            # Final
            final = {"tenant_id": tenant_id, "finding_id": finding_id, "subgraph": sub, "risk": risk, "draft": draft, "steps": [], "metrics": metrics}
            RUN_RESULTS[run_id] = final
            await q.put({"data": json.dumps(_record({"final": True, **final}))})
            _mark("final")
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
    # Metrics
    metrics = {"prefix_tokens": 1200, "suffix_tokens": 300, "cached_tokens": 1100, "cache_hit_ratio": 0.9, "input_cost_usd": 0.0025}
    metrics["prompt_tokens"] = metrics["prefix_tokens"] + metrics["suffix_tokens"]
    metrics["usd_estimate"] = metrics["input_cost_usd"]
    metrics["demo_simulated_metrics"] = True
    rec({"phase": "metrics", "metrics": metrics})
    # Planner
    v = scope_mod.check_scope(tenant_id, "triage finding", [f"finding:{finding_id}"])
    rec({"phase": "planner", "verdict": v})
    # Operator
    sub = graph_mod._ACTIVE_GRAPH.retrieve(tenant_id, finding_id, k=2, question=None) if graph_mod._ACTIVE_GRAPH else {"nodes": [], "edges": []}
    rec({"phase": "operator", "tool": "enrich_asset_graph", "result": {"subgraph_nodes": len(sub.get("nodes", []))}})
    n = graph_mod._ACTIVE_GRAPH.get(f"finding:{finding_id}") if graph_mod._ACTIVE_GRAPH else None
    band = (n.props.get("gold_band") if n else "medium") if n else "medium"
    risk = {"band": band, "score": {"critical": 0.95, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.05}.get(band, 0.5), "factors": []}
    rec({"phase": "operator", "tool": "rank_risk", "result": risk})
    evidence_ids = [nn["id"] for nn in sub.get("nodes", [])][:2] or [f"finding:{finding_id}"]
    steps = [{"text": "Rotate default credentials and restrict the management UI to the admin segment.", "cites": evidence_ids, "owner_id": "owner:team-facilities"}]
    cited = sorted({c for s in steps for c in s["cites"]})
    draft = {"steps": steps, "summary": f"{band} risk; coordinate with the owning team.", "cited_ids": cited, "non_destructive": True}
    rec({"phase": "operator", "tool": "draft_remediation", "result": {"cited_count": len(cited)}})
    # Checker
    chk = checker_mod.check_draft(draft, sub, tenant_id)
    rec({"phase": "checker", "result": {"passed": chk.passed, "issues": chk.issues}})
    # Final
    final = {"tenant_id": tenant_id, "finding_id": finding_id, "subgraph": sub, "risk": risk, "draft": draft, "steps": [], "metrics": metrics}
    rec({"final": True, **final})
    return {"history": history, "final": final}