"""Each triage run opens a real span. Export waits for DataRobot settings."""
from agent.monitoring import configure, export_configured, finished_spans, record_run


def test_a_run_opens_a_span_without_datarobot(monkeypatch):
    for key in ("DATAROBOT_API_TOKEN", "DATAROBOT_ENTITY_ID", "DATAROBOT_OTEL_ENDPOINT", "DATAROBOT_ENDPOINT"):
        monkeypatch.delenv(key, raising=False)
    configure()
    before = len(finished_spans())
    recorded = record_run(
        finding_id="F-101",
        tenant_id="tenant_demo_acme",
        model="gpt-5.6-terra",
        prompt_tokens=12,
        completion_tokens=4,
        completion="Hold v3.",
        checker_passed=True,
    )
    assert recorded["span"] == "casework.run"
    assert recorded["exported"] is False
    span = finished_spans()[-1]
    assert len(finished_spans()) == before + 1
    assert span["name"] == "casework.run"
    assert span["attributes"]["finding_id"] == "F-101"
    assert span["attributes"]["gen_ai.request.model"] == "gpt-5.6-terra"
    assert span["attributes"]["gen_ai.usage.prompt_tokens"] == 12
    assert span["attributes"]["checker.passed"] is True


def test_export_is_on_only_when_datarobot_is_fully_set(monkeypatch):
    monkeypatch.setenv("DATAROBOT_API_TOKEN", "test-token")
    monkeypatch.setenv("DATAROBOT_ENTITY_ID", "experiment_container-demo")
    monkeypatch.delenv("DATAROBOT_OTEL_ENDPOINT", raising=False)
    monkeypatch.delenv("DATAROBOT_ENDPOINT", raising=False)
    assert export_configured() is False
    monkeypatch.setenv("DATAROBOT_ENDPOINT", "https://app.datarobot.com/api/v2")
    assert export_configured() is True
