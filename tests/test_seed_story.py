"""Demo queue matches the script: F-101..F-107 in Acme, F-901 stays foreign."""
from pathlib import Path

from agent import graph as graph_mod

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed_graph.json"


def _graph():
    return graph_mod.load_seed(SEED)


def test_acme_queue_has_demo_findings_only():
    g = _graph()
    acme = {
        n.id
        for n in g._nodes.values()
        if n.type == "finding" and n.tenant_id == "tenant_demo_acme"
    }
    for n in range(101, 110):
        assert f"finding:F-{n}" in acme
    assert "finding:F-901" not in acme
    assert g.tenant_of("finding:F-901") == "tenant_other_corp"


def test_f101_neighborhood_shows_the_other_model():
    g = _graph()
    f101 = g.get("finding:F-101")
    assert "loan model" in f101.props["title"].lower()
    assert "Emirates NBD Demo" in f101.props["ask"]
    assert "4 more defaults" in f101.props["ask"]
    sub = g.retrieve("tenant_demo_acme", "F-101", k=3)
    ids = {n["id"] for n in sub["nodes"]}
    labels = {n["label"] for n in sub["nodes"]}
    assert {"asset:cam-01", "asset:cam-02", "segment:seg-dmz-a", "finding:F-105"} <= ids
    assert {"Loan model v3", "Loan model v2", "Personal loans"} <= labels
    assert "finding:F-901" not in ids
    assert not any(i.startswith("asset:oc-") for i in ids)


def test_snapshot_is_the_whole_bank_and_nothing_else():
    g = _graph()
    snap = g.snapshot("tenant_demo_acme")
    ids = {n["id"] for n in snap["nodes"]}
    assert snap["counts"]["nodes"] == len(ids) == 24
    assert "finding:F-101" in ids and "finding:F-901" not in ids
    assert all(e["src"] in ids and e["dst"] in ids for e in snap["edges"])
    assert snap["counts"]["edges"] == len(snap["edges"])
    other = g.snapshot("tenant_other_corp")
    assert {n["id"] for n in other["nodes"]} == {"finding:F-901", "asset:oc-01", "segment:oc-seg-1"}
