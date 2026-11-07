"""Open a span for each triage run and send it when DataRobot is configured."""
from __future__ import annotations

import os
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

_READY = False
_SPANS: list[dict[str, Any]] = []


def _endpoint() -> str:
    endpoint = os.environ.get("DATAROBOT_OTEL_ENDPOINT", "").rstrip("/")
    if endpoint:
        return endpoint
    api = os.environ.get("DATAROBOT_ENDPOINT", "").rstrip("/")
    if api.endswith("/api/v2"):
        api = api[: -len("/api/v2")]
    return f"{api}/otel" if api else ""


def export_configured() -> bool:
    token = os.environ.get("DATAROBOT_API_TOKEN", "")
    entity = os.environ.get("DATAROBOT_ENTITY_ID", "")
    return bool(token and entity and _endpoint())


class _Remember(SpanProcessor):
    def on_start(self, span, parent_context=None):
        return None

    def on_end(self, span):
        _SPANS.append({
            "name": span.name,
            "attributes": {key: span.attributes[key] for key in span.attributes},
            "exported": export_configured(),
        })

    def shutdown(self):
        return None

    def force_flush(self, timeout_millis=30000):
        return True


def finished_spans() -> list[dict[str, Any]]:
    return list(_SPANS)


def configure() -> None:
    global _READY
    if _READY:
        return
    provider = TracerProvider()
    provider.add_span_processor(_Remember())
    if export_configured():
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        headers = {
            "X-DataRobot-Entity-Id": os.environ["DATAROBOT_ENTITY_ID"],
            "X-DataRobot-Api-Key": os.environ["DATAROBOT_API_TOKEN"],
        }
        provider.add_span_processor(SimpleSpanProcessor(
            OTLPSpanExporter(endpoint=f"{_endpoint()}/v1/traces", headers=headers)
        ))
    trace.set_tracer_provider(provider)
    _READY = True


def record_run(
    *,
    finding_id: str,
    tenant_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    completion: str,
    checker_passed: bool,
) -> dict[str, Any]:
    configure()
    tracer = trace.get_tracer("casework")
    with tracer.start_as_current_span("casework.run") as span:
        span.set_attribute("finding_id", finding_id)
        span.set_attribute("tenant_id", tenant_id)
        span.set_attribute("gen_ai.request.model", model or "")
        span.set_attribute("gen_ai.usage.prompt_tokens", int(prompt_tokens or 0))
        span.set_attribute("gen_ai.usage.completion_tokens", int(completion_tokens or 0))
        span.set_attribute("gen_ai.completion", (completion or "")[:4000])
        span.set_attribute("checker.passed", bool(checker_passed))
        span.set_attribute("tool_name", "draft_remediation")
    return {"span": "casework.run", "exported": export_configured()}
