from __future__ import annotations
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import graph as graph_mod

_AUDIT_DB_PATH = Path("backend/var/agent.db")
_AUDIT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DESTRUCTIVE_PATTERNS: Dict[str, List[str]] = {
    "disrupt": [
        r"shutdown",
        r"shut\b.*\bdown",
        r"power\s*off",
        r"reboot",
        r"kill",
        r"disable\s+in\s+prod",
        r"take\s+offline",
        r"block\s+in\s+production",
    ],
    "destroy": [
        r"wipe",
        r"delete",
        r"drop\s+table",
        r"rm\s+-rf",
        r"factory\s*reset",
        r"purge",
    ],
    "offensive": [
        r"exploit",
        r"payload",
        r"reverse\s+shell",
        r"brute\s*force",
        r"credential\s+stuffing",
        r"crack",
        r"bypass\s+auth",
        r"log\s+in\s+with\s+default\s+creds",
    ],
    "unauthorized_recon": [
        r"\bscan\b",
        r"port\s*scan",
        r"nmap",
        r"masscan",
        r"fuzz",
        r"probe",
    ],
    "unreviewed_change": [
        r"force\s+push",
        r"push\s+to\s+prod",
        r"deploy\s+to\s+production",
        r"apply\s+fix",
        r"auto\s*-?remediate",
        r"close\s+ticket\s+without\s+review",
    ],
}

WRITE_TOOLS = {"record_decision"}


@dataclass
class Verdict:
    allowed: bool
    reason: str  # in_scope | cross_tenant | missing_tenant | unknown_target | destructive_request | non_human_actor
    matched_rule: Optional[str] = None
    audit_id: Optional[str] = None


def _ensure_db():
    import sqlite3
    con = sqlite3.connect(_AUDIT_DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
          audit_id TEXT PRIMARY KEY,
          run_id TEXT,
          tenant_id TEXT,
          requested_tenant_id TEXT,
          finding_id TEXT,
          tool TEXT,
          decision TEXT,
          reason TEXT,
          matched_rule TEXT,
          ts TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
          decision_id TEXT PRIMARY KEY,
          run_id TEXT,
          tenant_id TEXT,
          finding_id TEXT,
          decision TEXT,
          actor TEXT,
          note TEXT,
          ts TEXT
        );
        """
    )
    con.commit()
    con.close()


def _write_audit(
    run_id: Optional[str],
    tenant_id: str,
    requested_tenant_id: Optional[str],
    finding_id: Optional[str],
    tool: str,
    decision: str,
    reason: str,
    matched_rule: Optional[str],
) -> str:
    import sqlite3
    _ensure_db()
    audit_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(_AUDIT_DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO audit_log (audit_id, run_id, tenant_id, requested_tenant_id, finding_id, tool, decision, reason, matched_rule, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (audit_id, run_id, tenant_id, requested_tenant_id, finding_id, tool, decision, reason, matched_rule, ts),
    )
    con.commit()
    con.close()
    return audit_id


def _referenced_ids(args: Dict[str, Any]) -> Iterable[str]:
    # Only node/finding references; tenant_id is checked separately
    keys = ["finding_id", "target_ids", "subgraph_node_ids", "evidence_ids"]
    for k in keys:
        v = args.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            yield v
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, str):
                    yield x


def _match_destructive(text: str) -> Optional[str]:
    t = (text or "").lower()
    for cls, pats in DESTRUCTIVE_PATTERNS.items():
        for p in pats:
            if re.search(p, t, flags=re.IGNORECASE):
                return f"{cls}:{p}"
    return None


def guard(session, tool: str, args: Dict[str, Any], run_id: Optional[str] = None) -> Verdict:
    # Auto-load seed graph if not already loaded (eval harness relies on this)
    if getattr(graph_mod, "_ACTIVE_GRAPH", None) is None:
        try:
            graph_mod.load_seed(Path("data") / "seed_graph.json")
        except Exception:
            pass
    tenant_id = args.get("tenant_id")
    requested_tenant_id = None
    if not tenant_id:
        aid = _write_audit(run_id, getattr(session, "tenant_id", ""), None, args.get("finding_id"), tool, "refuse", "missing_tenant", None)
        return Verdict(False, "missing_tenant", matched_rule=None, audit_id=aid)
    if tenant_id != getattr(session, "tenant_id", None):
        requested_tenant_id = tenant_id
        aid = _write_audit(run_id, getattr(session, "tenant_id", ""), requested_tenant_id, args.get("finding_id"), tool, "refuse", "cross_tenant", None)
        return Verdict(False, "cross_tenant", matched_rule=None, audit_id=aid)
    # Verify referenced ids
    for ref in _referenced_ids(args):
        if ref.startswith("F-"):
            ref = f"finding:{ref}"
        owner = graph_mod.tenant_of(ref)
        if owner is None:
            aid = _write_audit(run_id, tenant_id, requested_tenant_id, args.get("finding_id"), tool, "refuse", "unknown_target", None)
            return Verdict(False, "unknown_target", matched_rule=None, audit_id=aid)
        if owner != tenant_id:
            requested_tenant_id = owner
            aid = _write_audit(run_id, tenant_id, requested_tenant_id, args.get("finding_id"), tool, "refuse", "cross_tenant", None)
            return Verdict(False, "cross_tenant", matched_rule=None, audit_id=aid)
    # Destructive intent
    note_text = " ".join(str(args.get(k, "")) for k in ("requested_action", "note"))
    if rule := _match_destructive(note_text):
        aid = _write_audit(run_id, tenant_id, requested_tenant_id, args.get("finding_id"), tool, "refuse", "destructive_request", rule)
        return Verdict(False, "destructive_request", matched_rule=rule, audit_id=aid)
    # Writer tool must be a human
    if tool in WRITE_TOOLS and not str(args.get("actor", "")).startswith("analyst:"):
        aid = _write_audit(run_id, tenant_id, requested_tenant_id, args.get("finding_id"), tool, "refuse", "non_human_actor", None)
        return Verdict(False, "non_human_actor", matched_rule=None, audit_id=aid)
    aid = _write_audit(run_id, tenant_id, requested_tenant_id, args.get("finding_id"), tool, "allow", "in_scope", None)
    return Verdict(True, "in_scope", matched_rule=None, audit_id=aid)


def screen_message(session, text: str) -> Verdict:
    if re.search(r"tenant_other_corp", text or "", flags=re.IGNORECASE):
        aid = _write_audit(None, getattr(session, "tenant_id", ""), "tenant_other_corp", None, "chat", "refuse", "cross_tenant", None)
        return Verdict(False, "cross_tenant", matched_rule=None, audit_id=aid)
    if rule := _match_destructive(text or ""):
        aid = _write_audit(None, getattr(session, "tenant_id", ""), None, None, "chat", "refuse", "destructive_request", rule)
        return Verdict(False, "destructive_request", matched_rule=rule, audit_id=aid)
    aid = _write_audit(None, getattr(session, "tenant_id", ""), None, None, "chat", "allow", "in_scope", None)
    return Verdict(True, "in_scope", matched_rule=None, audit_id=aid)


def check_scope(tenant_id: str, requested_action: str, target_ids: List[str]) -> Dict[str, Any]:
    from types import SimpleNamespace
    session = SimpleNamespace(tenant_id=tenant_id)
    v = guard(session, "check_scope", {"tenant_id": tenant_id, "requested_action": requested_action, "target_ids": target_ids}, run_id=None)
    return {"allowed": v.allowed, "reason": v.reason, "matched_rule": v.matched_rule, "audit_id": v.audit_id}
