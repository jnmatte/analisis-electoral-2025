"""Implementación del método D'Hondt con cifra repartidora."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List

from .data_loader import PactResult


@dataclass(frozen=True)
class DhondtSeat:
    """Representa una cuota calculada en el método D'Hondt."""

    pact_code: str
    quotient: float
    divisor: int
    raw_votes: int


def dhondt_allocation(pacts: Iterable[PactResult], seats: int) -> Dict[str, int]:
    """Entrega el número de escaños que obtiene cada pacto."""

    quotients: List[DhondtSeat] = []
    for pact in pacts:
        if pact.votes <= 0:
            continue
        for divisor in range(1, seats + 1):
            quotients.append(
                DhondtSeat(
                    pact_code=pact.code,
                    quotient=pact.votes / divisor,
                    divisor=divisor,
                    raw_votes=pact.votes,
                )
            )

    quotients.sort(key=lambda seat: (-seat.quotient, -seat.raw_votes, seat.pact_code))
    winners = quotients[:seats]
    counter: Counter[str] = Counter(seat.pact_code for seat in winners)
    return dict(counter)


__all__ = ["dhondt_allocation", "DhondtSeat"]
