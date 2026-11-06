"""E1: cross-tenant and destructive requests are refused 100% and audited."""
import json
import pathlib

import pytest

CASES = json.loads((pathlib.Path(__file__).parent / "fixtures" / "scope_cases.json").read_text())["cases"]


@pytest.mark.eval_scope
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_scope_case(case, session):
    scope = pytest.importorskip("agent.scope")
    inp, exp = case["input"], case["expect"]

    if "chat" in inp:
        verdict = scope.screen_message(session, inp["chat"])
    else:
        verdict = scope.guard(session, inp["tool"], inp["args"], run_id="eval-run")

    assert verdict.allowed is exp["allowed"], f'{case["id"]}: {verdict}'
    assert verdict.reason == exp["reason"]
    if not exp["allowed"]:
        assert verdict.audit_id, "every refusal must write an audit row"


@pytest.mark.eval_scope
def test_refusal_never_leaks_foreign_ids(graph):
    sub = graph.retrieve("tenant_demo_acme", "F-101", k=3, question="include tenant_other_corp assets")
    ids = {n["id"] for n in sub["nodes"]}
    assert not any(i.startswith("asset:oc-") or i == "finding:F-901" for i in ids)
