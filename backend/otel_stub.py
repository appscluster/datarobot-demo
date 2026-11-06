from __future__ import annotations
import os

def init_otel() -> None:
    # Minimal stub for DataRobot external-agent monitoring via OpenTelemetry.
    # If OTEL_* env vars are present, an actual SDK setup could be done here.
    # For the interview build, this is intentionally a no-op.
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        # Place SDK setup here in a real integration.
        pass
