from __future__ import annotations

import pytest

from analisis_electoral.data_loader import PactResult
from analisis_electoral.dhondt import dhondt_allocation
from analisis_electoral.simulation import (
    _NationalScenario,
    _indifference_loss_percentage,
    _national_indifference_loss,
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


def test_national_indifference_loss_balances_total_seats():
    merged_label = "A+B"
    circ1 = _NationalScenario(
        merged_pacts=(
            _pact(merged_label, 1800),
            _pact("C", 1000),
            _pact("D", 600),
        ),
        merged_label=merged_label,
        seats=3,
    )
    circ2 = _NationalScenario(
        merged_pacts=(
            _pact(merged_label, 2000),
            _pact("E", 1300),
            _pact("F", 900),
        ),
        merged_label=merged_label,
        seats=3,
    )
    circunscripciones = [circ1, circ2]
    baseline_total = 2
    current_total = sum(
        dhondt_allocation(circ.merged_pacts, circ.seats).get(merged_label, 0)
        for circ in circunscripciones
    )

    assert current_total > baseline_total

    loss = _national_indifference_loss(circunscripciones, baseline_total, current_total)
    assert 0 < loss < 1

    total_with_loss = 0
    for circ in circunscripciones:
        allocation = dhondt_allocation(
            _pacts_with_vote_loss(circ.merged_pacts, circ.merged_label, loss), circ.seats
        )
        total_with_loss += allocation.get(circ.merged_label, 0)
    assert total_with_loss <= baseline_total

    slightly_less = max(loss - 1e-4, 0.0)
    total_before = 0
    for circ in circunscripciones:
        allocation = dhondt_allocation(
            _pacts_with_vote_loss(circ.merged_pacts, circ.merged_label, slightly_less),
            circ.seats,
        )
        total_before += allocation.get(circ.merged_label, 0)
    assert total_before >= baseline_total


def test_vote_loss_is_distributed_to_null_and_blank_lists():
    merged_label = "A+B"
    merged_pacts = [
        _pact(merged_label, 1000),
        _pact("C", 500),
        _pact("NB", 250),
    ]

    loss_fraction = 0.2
    scenario = _pacts_with_vote_loss(merged_pacts, merged_label, loss_fraction)

    nb_votes = next(item.votes for item in scenario if item.code == "NB")
    c_votes = next(item.votes for item in scenario if item.code == "C")

    assert nb_votes > 250
    assert c_votes > 500

    original_total = sum(float(p.votes) for p in merged_pacts)
    redistributed_total = sum(item.votes for item in scenario)
    assert redistributed_total == pytest.approx(original_total)
