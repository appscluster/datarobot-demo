"""Unit tests for the scanner adapters (Gitleaks, TruffleHog, Trivy, Semgrep, Prowler).

Fixture values are obvious demo strings, not token shapes.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import security_sources as sec  # noqa: E402
from agent import graph as graph_mod  # noqa: E402
from agent import checker as checker_mod  # noqa: E402

FX = ROOT / "data" / "security_fixtures"
T = "tenant_demo_acme"
FAKE_GH = "demo-github-token-not-real"
FAKE_AWS = "demo-aws-key-not-real"


def _fx(tool):
    return sec.parse_file(FX / f"{tool}.json", T)


def _dump(findings):
    return json.dumps([f.to_dict() for f in findings])


def test_gitleaks_fixture_parses_and_redacts():
    fs = _fx("gitleaks")
    assert len(fs) == 2
    f = fs[0]
    assert f.source_tool == "gitleaks" and f.category == "secret" and f.severity == "high"
    assert f.rule_id == "github-pat" and f.file == "services/notifier/config.py" and f.line == 14
    assert f.finding_id.startswith("F-GL-") and f.synthetic
    raw = json.loads((FX / "gitleaks.json").read_text())["report"]
    for r in raw:
        assert r["Secret"] not in _dump(fs)
        assert r["Match"] not in _dump(fs)
    assert f.masked_preview.startswith("demo") and "*" in f.masked_preview


def test_trufflehog_fixture_unverified_high_and_redacted():
    fs = _fx("trufflehog")
    assert {f.rule_id for f in fs} == {"AWS (unverified)", "SlackWebhook (unverified)"}
    assert all(f.severity == "high" for f in fs)
    assert fs[0].file == "scripts/legacy_upload.sh" and fs[0].line == 7
    blob = _dump(fs)
    for r in json.loads((FX / "trufflehog.json").read_text())["report"]:
        assert r["Raw"] not in blob
        if r.get("RawV2"):
            assert r["RawV2"] not in blob


def test_trufflehog_verified_is_critical_and_skips_log_lines():
    rows = [{"level": "info", "msg": "running"},
            {"DetectorName": "Github", "Verified": True, "Raw": FAKE_GH,
             "SourceMetadata": {"Data": {"Git": {"file": "a.py", "line": 3, "commit": "abc"}}}}]
    fs = sec.parse_trufflehog(rows, T)
    assert len(fs) == 1 and fs[0].severity == "critical" and fs[0].file == "a.py"
    assert FAKE_GH not in _dump(fs)


def test_trivy_fixture_vulns_and_misconfig():
    fs = _fx("trivy")
    by_rule = {f.rule_id: f for f in fs}
    assert set(by_rule) == {"CVE-2099-0001", "CVE-2099-0002", "AVD-DS-0002"}
    assert by_rule["CVE-2099-0001"].severity == "high" and "1.2.5" in by_rule["CVE-2099-0001"].remediation
    assert by_rule["CVE-2099-0001"].weakness_id == "weakness:CWE-444"
    assert by_rule["AVD-DS-0002"].category == "misconfig" and by_rule["AVD-DS-0002"].line == 1


def test_trivy_secret_is_redacted():
    rep = {"ArtifactName": "x", "ArtifactType": "filesystem", "Results": [{"Target": "app.env", "Secrets": [
        {"RuleID": "aws-access-key-id", "Severity": "CRITICAL", "StartLine": 2, "Match": f"KEY={FAKE_AWS}",
         "Code": {"Lines": [{"Content": f"KEY={FAKE_AWS}"}]}}]}]}
    fs = sec.parse_trivy(rep, T)
    assert len(fs) == 1 and fs[0].severity == "critical" and fs[0].category == "secret"
    assert FAKE_AWS not in _dump(fs)


def test_semgrep_fixture_maps_severity_and_cwe():
    fs = _fx("semgrep")
    assert len(fs) == 2
    sh = [f for f in fs if "subprocess" in f.rule_id][0]
    assert sh.severity == "high" and sh.weakness_id == "weakness:CWE-78" and sh.line == 41
    xss = [f for f in fs if "dangerously" in f.rule_id][0]
    assert xss.severity == "medium" and xss.weakness_id == "weakness:CWE-79"


def test_semgrep_never_stores_matched_lines():
    rep = {"results": [{"check_id": "generic.secrets.x", "path": "a.py", "start": {"line": 1},
                        "extra": {"severity": "ERROR", "message": "secret", "lines": f"tok = '{FAKE_GH}'"}}]}
    assert FAKE_GH not in _dump(sec.parse_semgrep(rep, T))


def test_prowler_ocsf_fixture_only_fail():
    fs = _fx("prowler")
    assert len(fs) == 2  # the PASS row is skipped
    assert {f.severity for f in fs} == {"high", "medium"}
    assert all(f.asset_id == "asset:cloud-aws-000000000000" for f in fs)


def test_prowler_legacy_json():
    rows = [{"Status": "FAIL", "Severity": "critical", "CheckID": "iam_root_mfa_enabled", "CheckTitle": "Root MFA",
             "ResourceId": "root", "AccountId": "000000000000", "Provider": "aws", "Region": "us-east-1"},
            {"Status": "PASS", "Severity": "low", "CheckID": "x"}]
    fs = sec.parse_prowler(rows, T)
    assert len(fs) == 1 and fs[0].severity == "critical" and fs[0].rule_id == "iam_root_mfa_enabled"


def test_mask_secret_never_returns_full_value():
    assert sec.mask_secret(FAKE_GH) != FAKE_GH and FAKE_GH[8:] not in sec.mask_secret(FAKE_GH)
    assert sec.mask_secret("short") == "********"
    assert sec.mask_secret(None) is None


def test_store_redaction_and_tenant_scoping(tmp_path):
    db = tmp_path / "sec.db"
    gl = [{"RuleID": "github-pat", "File": "x.py", "StartLine": 1, "Secret": FAKE_GH, "Match": f"t='{FAKE_GH}'"}]
    th = [{"DetectorName": "AWS", "Verified": False, "Raw": FAKE_AWS,
           "SourceMetadata": {"Data": {"Filesystem": {"file": "y.sh", "line": 2}}}}]
    sec.store(sec.parse_gitleaks(gl, T) + sec.parse_trufflehog(th, T), db)
    sec.store(sec.parse_gitleaks(gl, "tenant_other_corp", project="Other"), db)
    con = sqlite3.connect(db)
    dump = "\n".join(repr(r) for r in con.execute("SELECT * FROM security_findings"))
    con.close()
    assert FAKE_GH not in dump and FAKE_AWS not in dump
    assert db.read_bytes().find(FAKE_GH.encode()) == -1 and db.read_bytes().find(FAKE_AWS.encode()) == -1
    mine = sec.load(db, T)
    assert len(mine) == 2 and all(f.tenant_id == T for f in mine)
    assert len(sec.load(db, "tenant_other_corp")) == 1


def test_collect_auto_falls_back_to_fixtures(tmp_path):
    fs, files = sec.collect("auto", T, reports_dir=tmp_path / "missing")
    assert len(files) == 5
    assert {f.source_tool for f in fs} == set(sec.TOOLS)


def test_graph_merge_tenant_scoped_and_checker_passes():
    g = graph_mod.load_seed(ROOT / "data" / "seed_graph.json")
    fs, _ = sec.collect("fixtures", T)
    other = sec.parse_file(FX / "semgrep.json", "tenant_other_corp")
    for f in other:
        f.asset_id = "asset:repo-OtherCorp"
    assert sec.merge_into_graph(g, fs + other) == len(fs) + len(other)
    fid = [f for f in fs if f.source_tool == "gitleaks"][0].finding_id
    sub = g.retrieve(T, fid, k=2)
    ids = {n["id"] for n in sub["nodes"]}
    assert f"finding:{fid}" in ids and "asset:repo-DataRobot-Demo" in ids and "tool:gitleaks" in ids
    assert any(i.startswith("asset:file-services-notifier-config-py") for i in ids)
    assert ("asset:file" in [e["src"][:10] for e in sub["edges"] if e["type"] == "SCANNED_BY" and e["dst"] == "tool:gitleaks"][0])
    assert all(g.tenant_of(i) == T for i in ids)
    # cross tenant: our tenant cannot retrieve the foreign finding
    assert g.retrieve(T, other[0].finding_id, k=2)["nodes"] == []
    # the default draft (first two nodes) cites finding and asset and passes the checker
    node = g.get(f"finding:{fid}")
    evidence = [n["id"] for n in sub["nodes"]][:2]
    draft = {"steps": [{"text": node.props["remediation"], "cites": evidence, "owner_id": node.props["owner_id"]}],
             "cited_ids": sorted(evidence), "non_destructive": True}
    assert checker_mod.check_draft(draft, sub, T).passed
    graph_mod.load_seed(ROOT / "data" / "seed_graph.json")  # leave the seed graph clean


def test_safe_remediation_rewrites_destructive_advice():
    assert "delete" not in sec.safe_remediation("delete the bucket", "cloud").lower()
    assert sec.safe_remediation("Upgrade foo to 1.2", "dependency") == "Upgrade foo to 1.2"
