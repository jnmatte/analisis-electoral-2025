from __future__ import annotations

from analisis_electoral.data_loader import PactResult
from analisis_electoral.dhondt import dhondt_allocation
from analisis_electoral.simulation import (
    _indifference_loss_percentage,
    _pacts_with_vote_loss,
)


def _pact(code: str, votes: int) -> PactResult:
    return PactResult(
        code=code,
        name=code,
        label=code,
        votes=votes,
        percentage=None,
        candidate_slots=None,
        seats_won=None,
        candidates=[],
    )


def test_indifference_loss_matches_expected_threshold():
    merged_label = "A+B"
    merged_pacts = [
        _pact(merged_label, 1800),
        _pact("C", 1000),
        _pact("D", 600),
    ]
    seats = 3
    baseline_seats = 1
    current_seats = 2

    loss = _indifference_loss_percentage(
        merged_pacts,
        merged_label,
        seats,
        baseline_seats,
        current_seats,
    )

    assert 0 < loss < 1

    scenario = dhondt_allocation(
        _pacts_with_vote_loss(merged_pacts, merged_label, loss), seats
    )
    assert scenario.get(merged_label, 0) <= baseline_seats

    slightly_less = max(loss - 1e-4, 0.0)
    previous = dhondt_allocation(
        _pacts_with_vote_loss(merged_pacts, merged_label, slightly_less), seats
    )
    assert previous.get(merged_label, 0) >= baseline_seats


def test_indifference_loss_is_zero_when_scenario_not_better():
    merged_label = "A+B"
    merged_pacts = [
        _pact(merged_label, 1000),
        _pact("C", 1200),
    ]
    seats = 2
    baseline_seats = 1
    current_seats = 1

    loss = _indifference_loss_percentage(
        merged_pacts,
        merged_label,
        seats,
        baseline_seats,
        current_seats,
    )

    assert loss == 0.0
