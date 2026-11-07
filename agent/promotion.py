"""A request to put the challenger live. The live scorer does not change."""
from dataclasses import replace

from agent.scoring import ScoringState


def request_promotion(state: ScoringState, actor: str) -> tuple[ScoringState, str]:
    if not actor:
        raise ValueError("actor required")
    return replace(state, regions=dict(state.regions)), "promotion_refused"
