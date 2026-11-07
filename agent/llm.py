"""OpenAI-compatible chat calls. Default route is the local OmniRoute gateway."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List


def settings() -> Dict[str, Any]:
    return {
        "base_url": os.environ.get("LLM_BASE_URL", "http://127.0.0.1:20128/v1").rstrip("/"),
        "model": os.environ.get("LLM_MODEL", "gh/gpt-5.6-terra"),
        "timeout": float(os.environ.get("LLM_TIMEOUT_SECONDS", "90")),
    }


def chat(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    cfg = settings()
    body = {"model": cfg["model"], "messages": messages, "max_tokens": 700}
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    key = os.environ.get("LLM_API_KEY")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
        data = json.loads(resp.read().decode())
    message = (data.get("choices") or [{}])[0].get("message") or {}
    content = message.get("content") or ""
    if not str(content).strip():
        raise RuntimeError("model returned an empty reply")
    return {
        "content": content,
        "model": data.get("model") or cfg["model"],
        "usage": data.get("usage") or {},
    }
