"""Ask the model for the customer reply. Citations stay inside the graph."""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from . import checker as checker_mod
from . import llm as llm_mod

Complete = Callable[[List[Dict[str, str]]], Dict[str, Any]]

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def for_draft(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], finding_id: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Keep this request. Drop other requests that share an asset."""
    anchor = finding_id if str(finding_id).startswith("finding:") else f"finding:{finding_id}"
    kept = [node for node in nodes if node.get("type") != "finding" or node.get("id") == anchor]
    ids = {node.get("id") for node in kept}
    kept_edges = [edge for edge in edges if edge.get("src") in ids and edge.get("dst") in ids]
    return kept, kept_edges


def case_messages(
    finding_id: str,
    title: str,
    ask: str,
    band: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    decision: str = "",
) -> List[Dict[str, str]]:
    allowed = [n.get("id") for n in nodes if n.get("id")]
    system = (
        "You draft a reply a credit analyst can send later. You do not change production, "
        "promote a model, or take any system offline. Use only facts in the case. "
        "The reply must follow the decision. Do not mention any other request. "
        "Cite only ids from the allowed list. Reply with JSON only, no markdown: "
        '{"text": "two to four sentences", "cites": ["finding:F-104"]}. '
        "Do not use these words: shut down, shutdown, delete, wipe, reboot, scan, exploit, payload."
    )
    user = json.dumps({
        "finding_id": finding_id,
        "title": title,
        "ask": ask,
        "band": band,
        "decision": decision,
        "allowed_ids": allowed,
        "nodes": nodes,
        "edges": edges[:12],
    }, ensure_ascii=True)
    built = [SystemMessage(content=system), HumanMessage(content=user)]
    return [{"role": "user" if message.type == "human" else message.type, "content": str(message.content)} for message in built]


def _loads(content: str) -> Dict[str, Any]:
    raw = _FENCE.sub("", (content or "").strip())
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return {"text": raw, "cites": []}
        try:
            data = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return {"text": raw, "cites": []}
    return data if isinstance(data, dict) else {"text": raw, "cites": []}


def _cites(raw: Any, allowed: set[str], fallback: List[str]) -> List[str]:
    picked = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item in allowed and checker_mod.NODE_ID_RE.match(item):
                picked.append(item)
    if not picked:
        picked = [c for c in fallback if c in allowed and checker_mod.NODE_ID_RE.match(c)]
    return sorted(set(picked))


def _unsafe(text: str) -> bool:
    return any(re.search(p, text or "", flags=re.IGNORECASE) for p in checker_mod._DESTRUCTIVE_HINTS)


def _metrics(usage: Dict[str, Any], model: str, calls: int) -> Dict[str, Any]:
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    cached = int(usage.get("cached_tokens") or details.get("cached_tokens") or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "prefix_tokens": prompt,
        "suffix_tokens": completion,
        "cached_tokens": cached,
        "cache_hit_ratio": (cached / prompt) if prompt else 0,
        "usd_estimate": None,
        "demo_simulated_metrics": False,
        "model": model,
        "provider": "omniroute",
        "calls": calls,
    }


def _add_usage(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(left)
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"):
        out[key] = int(left.get(key) or 0) + int(right.get(key) or 0)
    return out


def draft_case(
    finding_id: str,
    title: str,
    ask: str,
    band: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    evidence_ids: List[str],
    owner_id: str,
    complete: Optional[Complete] = None,
    decision: str = "",
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    complete = complete or llm_mod.chat
    nodes, edges = for_draft(nodes, edges, finding_id)
    allowed = {n.get("id") for n in nodes if n.get("id")}
    messages = case_messages(finding_id, title, ask, band, nodes, edges, decision=decision)
    first = complete(messages)
    parsed = _loads(first.get("content") or "")
    text = str(parsed.get("text") or "").strip()
    cites = _cites(parsed.get("cites"), allowed, evidence_ids)
    usage = dict(first.get("usage") or {})
    model = str(first.get("model") or "")
    calls = 1
    if _unsafe(text):
        rewrite = messages + [
            {"role": "assistant", "content": first.get("content") or ""},
            {"role": "user", "content": "Rewrite the JSON. Remove every instruction that changes or stops a live system. Keep the cites."},
        ]
        second = complete(rewrite)
        parsed = _loads(second.get("content") or "")
        rewritten = str(parsed.get("text") or "").strip()
        if rewritten and not _unsafe(rewritten):
            text = rewritten
            cites = _cites(parsed.get("cites"), allowed, evidence_ids)
        usage = _add_usage(usage, second.get("usage") or {})
        model = str(second.get("model") or model)
        calls = 2
    if not text:
        raise RuntimeError("model returned an empty reply")
    if not cites:
        raise RuntimeError("model reply cited no graph ids")
    draft = {
        "steps": [{"text": text, "cites": cites, "owner_id": owner_id}],
        "summary": f"{band or 'medium'} priority. The reply stays a draft until a person decides.",
        "cited_ids": cites,
        "non_destructive": True,
        "model": model,
        "provider": "omniroute",
    }
    return draft, _metrics(usage, model, calls)
