"""E2: drafts cite >=1 real in-tenant node id; checker catches missing/invalid citations."""
import re

import pytest

from conftest import NODE_ID_RE


def _draft(steps):
    cited = sorted({c for s in steps for c in s["cites"]})
    return {"steps": steps, "summary": "", "cited_ids": cited, "non_destructive": True}


@pytest.mark.eval_citation
def test_checker_flags_missing_citation(graph):
    checker = pytest.importorskip("agent.checker")
    sub = graph.retrieve("tenant_demo_acme", "F-101", k=2, question=None)
    bad = _draft([{"text": "Rotate default credentials on the camera.", "cites": [], "owner_id": None}])
    res = checker.check_draft(bad, sub, "tenant_demo_acme")
    assert not res.passed and "missing_citation" in res.issues


@pytest.mark.eval_citation
def test_checker_flags_invented_id(graph):
    checker = pytest.importorskip("agent.checker")
    sub = graph.retrieve("tenant_demo_acme", "F-101", k=2, question=None)
    bad = _draft([{"text": "Restrict UI on cam-77.", "cites": ["asset:cam-77"], "owner_id": None}])
    res = checker.check_draft(bad, sub, "tenant_demo_acme")
    assert not res.passed and "invalid_id" in res.issues


@pytest.mark.eval_citation
def test_checker_passes_grounded_draft(graph):
    checker = pytest.importorskip("agent.checker")
    sub = graph.retrieve("tenant_demo_acme", "F-101", k=2, question=None)
    good = _draft([{"text": "Rotate default credentials and restrict the management UI to the admin segment.",
                    "cites": ["asset:cam-01", "segment:seg-dmz-a"], "owner_id": "owner:team-facilities"}])
    assert all(re.match(NODE_ID_RE, c) for c in good["cited_ids"])
    assert checker.check_draft(good, sub, "tenant_demo_acme").passed
