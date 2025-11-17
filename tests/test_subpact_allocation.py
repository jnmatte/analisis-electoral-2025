"""Pruebas para la asignación de escaños por subpactos."""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from analisis_electoral.data_loader import CandidateResult, PactResult
from analisis_electoral.simulation import _winners_by_pact


def _candidate(number: int, name: str, party: str, votes: int, pact_code: str) -> CandidateResult:
    return CandidateResult(
        number=number,
        name=name,
        party=party,
        votes=votes,
        percentage=None,
        elected=False,
        pact_code=pact_code,
    )


def test_subpact_allocation_uses_party_votes():
    pact_code = "PX"
    pact = PactResult(
        code=pact_code,
        name="Pacto X",
        label=pact_code,
        votes=3400,
        percentage=None,
        candidate_slots=None,
        seats_won=None,
        candidates=[
            _candidate(1, "A1", "Partido A", 1000, pact_code),
            _candidate(2, "A2", "Partido A", 800, pact_code),
            _candidate(3, "B1", "Partido B", 900, pact_code),
            _candidate(4, "B2", "Partido B", 700, pact_code),
        ],
    )

    allocation = {pact_code: 2}
    winners = _winners_by_pact([pact], allocation)
    assert [candidate.name for candidate in winners[pact_code]] == ["A1", "B1"]


def test_candidates_without_party_are_still_selected_by_votes():
    pact_code = "PI"
    pact = PactResult(
        code=pact_code,
        name="Pacto Independiente",
        label=pact_code,
        votes=3000,
        percentage=None,
        candidate_slots=None,
        seats_won=None,
        candidates=[
            _candidate(1, "Ind1", None, 2000, pact_code),
            _candidate(2, "Ind2", None, 1000, pact_code),
        ],
    )

    allocation = {pact_code: 2}
    winners = _winners_by_pact([pact], allocation)
    assert [candidate.name for candidate in winners[pact_code]] == ["Ind1", "Ind2"]
