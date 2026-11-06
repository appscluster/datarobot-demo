"""Shared fixtures for the ThreatAI eval harness (synthetic data only).

Interfaces imported here are the contract the scaffold must provide:
  agent.scope.guard(session, tool, args, run_id) -> Verdict(allowed, reason, matched_rule, audit_id)
  agent.scope.screen_message(session, text) -> Verdict
  agent.checker.check_draft(draft, subgraph, tenant_id) -> CheckResult(passed, issues: list[str])
  agent.graph.load_seed(path) -> Graph ; Graph.retrieve(tenant_id, finding_id, k, question) -> Subgraph
Tests skip (not fail) until those modules exist.
"""
import json
import pathlib
from types import SimpleNamespace

import pytest

FIX = pathlib.Path(__file__).parent / "fixtures"
ROOT = pathlib.Path(__file__).resolve().parents[1]
SESSION_TENANT = "tenant_demo_acme"
FOREIGN_TENANT = "tenant_other_corp"
NODE_ID_RE = r"^(asset|finding|segment|owner|weakness):[A-Za-z0-9-]+$"


def _load(name):
    return json.loads((FIX / name).read_text())


@pytest.fixture(scope="session")
def gold():
    return _load("gold_findings.json")["findings"]


@pytest.fixture(scope="session")
def scope_cases():
    return _load("scope_cases.json")["cases"]


@pytest.fixture(scope="session")
def multihop():
    return _load("multihop_questions.json")["questions"]


@pytest.fixture
def session():
    return SimpleNamespace(tenant_id=SESSION_TENANT, actor="analyst:demo-1")


@pytest.fixture(scope="session")
def graph():
    g = pytest.importorskip("agent.graph")
    return g.load_seed(ROOT / "data" / "seed_graph.json")
