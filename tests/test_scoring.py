"""v2 scores the book. The holdout note is a labeled fact, not a recount."""
from agent.scoring import load_scoring


def test_v2_scores_the_book_and_the_west():
    state = load_scoring("data/scoring_state.json")
    assert state.live_model == "Loan model v2"
    assert state.region_model("west") == "Loan model v2"
    assert state.nightly_owner is None
    assert state.holdout_note == "4 more defaults per 100"
