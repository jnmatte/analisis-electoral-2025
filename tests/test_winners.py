from analisis_electoral.data_loader import CandidateResult, PactResult
from analisis_electoral.simulation import _candidate_subpact_code, _select_winners_from_pact


def _candidate(number: int, name: str, party: str, votes: int, pact_code: str = "C") -> CandidateResult:
    return CandidateResult(
        number=number,
        name=name,
        party=party,
        votes=votes,
        percentage=None,
        elected=False,
        pact_code=pact_code,
    )


def _pact(candidates):
    return PactResult(
        code="C",
        name="Unidad Por Chile",
        label="C - Unidad Por Chile",
        votes=sum(candidate.votes for candidate in candidates),
        percentage=None,
        candidate_slots=None,
        seats_won=None,
        candidates=list(candidates),
    )


def test_subpact_underallocation_fills_remaining_seats():
    candidates = [
        _candidate(1, "Daniella Cicardini", "PS", 66166),
        _candidate(2, "Yasna Provoste", "PDC", 30760),
    ]
    pact = _pact(candidates)

    winners = _select_winners_from_pact(pact, 2)

    assert [candidate.name for candidate in winners] == [
        "Daniella Cicardini",
        "Yasna Provoste",
    ]
    assert len(winners) == 2


def test_independent_with_party_counts_towards_party_subpact():
    candidate = _candidate(1, "Loreto Carvajal", "IND - PPD", 50000)

    assert _candidate_subpact_code(candidate) == "PPD"


def test_plain_independent_remains_its_own_subpact():
    candidate = _candidate(1, "Laura Iturriaga", "IND", 42000)

    assert _candidate_subpact_code(candidate) == "IND"
