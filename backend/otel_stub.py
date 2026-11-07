from __future__ import annotations

from agent.monitoring import configure


def init_otel() -> None:
    """Open the tracer for casework runs and export when DataRobot is configured."""
    configure()
