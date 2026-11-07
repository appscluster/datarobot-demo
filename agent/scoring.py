"""Which model scores the personal loan book. The challenger is not live."""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScoringState:
    live_model: str
    challenger_model: str
    regions: dict[str, str]
    nightly_owner: str | None
    holdout_note: str

    def region_model(self, region: str) -> str:
        return self.regions.get(region, self.live_model)


def load_scoring(path: str) -> ScoringState:
    raw = json.loads(Path(path).read_text())
    state = ScoringState(
        live_model=raw["live_model"],
        challenger_model=raw["challenger_model"],
        regions=dict(raw.get("regions") or {}),
        nightly_owner=raw.get("nightly_owner"),
        holdout_note=raw["holdout_note"],
    )
    if state.live_model == state.challenger_model:
        raise ValueError("the challenger must not be the live scorer")
    return state
