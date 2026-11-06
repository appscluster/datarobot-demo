from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List

NODE_ID_RE = re.compile(r"^(asset|finding|segment|owner|weakness):[A-Za-z0-9-]+$")

_DESTRUCTIVE_HINTS = [r"shut\s*down", r"shutdown", r"wipe", r"delete", r"drop\s+table", r"rm\s+-rf", r"reboot", r"exploit", r"payload", r"\bscan\b"]

@dataclass
class CheckResult:
    passed: bool
    issues: List[str]


def _collect_node_ids(subgraph: Dict[str, Any]) -> set[str]:
    return {n.get("id") for n in subgraph.get("nodes", []) if isinstance(n, dict) and n.get("id")}


def check_draft(draft: Dict[str, Any], subgraph: Dict[str, Any], tenant_id: str) -> CheckResult:
    issues: List[str] = []
    cited_ids: List[str] = list(draft.get("cited_ids") or [])
    if not cited_ids:
        issues.append("missing_citation")
    sub_ids = _collect_node_ids(subgraph)
    bad_ids = [c for c in cited_ids if (not NODE_ID_RE.match(c)) or (c not in sub_ids)]
    if bad_ids:
        issues.append("invalid_id")
    steps = draft.get("steps") or []
    txt = "\n".join(str(s.get("text", "")) for s in steps if isinstance(s, dict))
    if any(re.search(p, txt, flags=re.IGNORECASE) for p in _DESTRUCTIVE_HINTS):
        issues.append("unsafe_instruction")
    if not draft.get("non_destructive", False):
        issues.append("requires_non_destructive")
    return CheckResult(passed=len(issues) == 0, issues=issues)
