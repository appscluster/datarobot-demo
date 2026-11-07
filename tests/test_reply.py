"""The reply is produced by the model. The stored remediation is not the prompt."""
import json

from agent import reply


def test_prompt_uses_the_case_and_hides_the_stored_sentence():
    messages = reply.case_messages(
        finding_id="F-104",
        title="The new model still requires debt to income",
        ask="Loan model v3 still requires debt to income.",
        band="medium",
        nodes=[{"id": "finding:F-104", "type": "finding", "label": "F-104"}],
        edges=[],
    )
    blob = json.dumps(messages)
    assert "debt to income" in blob
    assert "finding:F-104" in blob
    assert "Keep v3 off the scoring path" not in blob
    assert "remediation" not in blob.lower()


def test_approval_draft_drops_the_other_request():
    nodes = [
        {"id": "finding:F-109", "type": "finding", "label": "F-109"},
        {"id": "finding:F-102", "type": "finding", "label": "F-102"},
        {"id": "asset:ps-web-01", "type": "asset", "label": "Application file"},
    ]
    edges = [
        {"src": "asset:ps-web-01", "type": "HAS_FINDING", "dst": "finding:F-109"},
        {"src": "asset:ps-web-01", "type": "HAS_FINDING", "dst": "finding:F-102"},
    ]
    kept, kept_edges = reply.for_draft(nodes, edges, "F-109")
    ids = {node["id"] for node in kept}
    assert "finding:F-102" not in ids
    assert "finding:F-109" in ids
    assert all(edge["dst"] != "finding:F-102" for edge in kept_edges)
    messages = reply.case_messages(
        "F-109",
        "Two complete applications can wait for the next batch",
        "A-1002 and A-1005 are complete.",
        "low",
        kept,
        kept_edges,
        decision="The next scheduled batch can include A-1002 and A-1005.",
    )
    blob = json.dumps(messages)
    assert "finding:F-102" not in blob
    assert "next scheduled batch" in blob


def test_draft_keeps_only_ids_the_graph_returned():
    def complete(messages):
        assert messages[0]["role"] == "system"
        return {
            "content": json.dumps({
                "text": "Hold v3 until debt to income is mapped. Leave the live score path as it is.",
                "cites": ["finding:F-104", "asset:not-real", "drop table"],
            }),
            "model": "gpt-5.6-terra",
            "usage": {"prompt_tokens": 40, "completion_tokens": 18, "total_tokens": 58},
        }

    draft, metrics = reply.draft_case(
        finding_id="F-104",
        title="The new model still requires debt to income",
        ask="Loan model v3 still requires debt to income.",
        band="medium",
        nodes=[
            {"id": "finding:F-104", "type": "finding", "label": "F-104"},
            {"id": "asset:cam-01", "type": "asset", "label": "Loan model v3"},
        ],
        edges=[],
        evidence_ids=["finding:F-104", "asset:cam-01"],
        owner_id="owner:team-facilities",
        complete=complete,
    )
    assert draft["model"] == "gpt-5.6-terra"
    assert draft["cited_ids"] == ["finding:F-104"]
    assert "Hold v3" in draft["steps"][0]["text"]
    assert metrics["demo_simulated_metrics"] is False
    assert metrics["prompt_tokens"] == 40
    assert metrics["provider"] == "omniroute"
