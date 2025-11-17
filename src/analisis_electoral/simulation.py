"""CLI para simular la unión de pactos en el sistema D'Hondt."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

if __package__ in (None, ""):
    # Permite ejecutar este archivo directamente (por ejemplo, desde Spyder)
    # añadiendo la carpeta raíz del paquete al ``sys.path``.
    PACKAGE_ROOT = Path(__file__).resolve().parents[1]
    if str(PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_ROOT))

from analisis_electoral.data_loader import (
    CandidateResult,
    CircunscripcionResult,
    PactResult,
    load_circunscripciones,
)
from analisis_electoral.dhondt import dhondt_allocation


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Simula cómo cambiaría la asignación de escaños si dos pactos electorales "
            "hubieran competido juntos."
        )
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        default=Path("Inputs/Senadores"),
        help="Carpeta que contiene los archivos Excel oficiales (Senadores o Diputados)",
    )
    parser.add_argument(
        "--circ",
        nargs="*",
        default=None,
        help="IDs de circunscripción a analizar (por ejemplo: 1 2 3). Si no se indica se usan todas.",
    )
    parser.add_argument("--pact-a", required=True, help="Código del primer pacto (por ejemplo C)")
    parser.add_argument("--pact-b", required=True, help="Código del segundo pacto (por ejemplo J)")
    args = parser.parse_args(argv)

    circunscripciones = load_circunscripciones(args.inputs)
    circ_filter = {cid for cid in args.circ} if args.circ else None
    pact_codes = {args.pact_a.strip().upper(), args.pact_b.strip().upper()}

    summary_official: Counter[str] = Counter()
    summary_scenario: Counter[str] = Counter()
    summary_scenario_by_origin: Counter[str] = Counter()
    summary_breakdowns: dict[str, Counter[str]] = defaultdict(Counter)
    pact_names: dict[str, str] = {}
    processed_any = False

    for circ in circunscripciones:
        if circ_filter and circ.circunscripcion_id not in circ_filter:
            continue

        original_allocation = dhondt_allocation(circ.pacts, circ.seats)
        _record_pact_names(pact_names, circ.pacts)
        try:
            merged_pacts, merged_label = _merge_pacts(circ.pacts, pact_codes)
        except ValueError as exc:
            print(f"\nNo fue posible crear el escenario: {exc}")
            continue
        merged_allocation = dhondt_allocation(merged_pacts, circ.seats)
        for pact in merged_pacts:
            pact_names.setdefault(pact.code, pact.name)
        processed_any = True

        original_winners = _winners_by_pact(circ.pacts, original_allocation)
        merged_winners = _winners_by_pact(merged_pacts, merged_allocation)
        has_changes = _has_result_changes(original_winners, merged_winners)

        merged_breakdown = _merged_breakdown_counts(merged_label, merged_winners)
        if merged_breakdown:
            summary_breakdowns[merged_label].update(merged_breakdown)

        summary_official.update(original_allocation)
        summary_scenario.update(merged_allocation)
        distributed_allocation = _distribute_allocation_by_origin(
            merged_allocation, merged_label, merged_breakdown
        )
        summary_scenario_by_origin.update(distributed_allocation)

        if not has_changes:
            continue

        print(f"\n=== {circ.circunscripcion_label} ({circ.seats} escaños) ===")
        _print_pact_table(circ.pacts)

        print("\n> Resultado oficial con los pactos originales:")
        _print_allocation(original_allocation, circ.pacts)

        print("\n> Escenario si se unen {0}:".format(" + ".join(sorted(pact_codes))))
        _print_allocation(merged_allocation, merged_pacts)

        _print_winners("Electos oficiales", original_winners)
        _print_winners("Electos en el escenario", merged_winners)
        _print_merged_breakdown(merged_label, merged_breakdown)

        if not has_changes:
            continue

        print(f"\n=== {circ.circunscripcion_label} ({circ.seats} escaños) ===")
        _print_pact_table(circ.pacts)

        print("\n> Resultado oficial con los pactos originales:")
        _print_allocation(original_allocation, circ.pacts)

        print("\n> Escenario si se unen {0}:".format(" + ".join(sorted(pact_codes))))
        _print_allocation(merged_allocation, merged_pacts)

        _print_winners("Electos oficiales", original_winners)
        _print_winners("Electos en el escenario", merged_winners)
        _print_merged_breakdown(merged_label, merged_breakdown)

    if processed_any:
        _print_summary(
            summary_official,
            summary_scenario,
            summary_scenario_by_origin,
            pact_names,
            summary_breakdowns,
        )


def _print_pact_table(pacts: Iterable[PactResult]) -> None:
    print("Pactos disponibles:")
    for pact in pacts:
        print(
            f" - {pact.code}: {pact.name} ({pact.votes:,} votos, {len(pact.candidates)} candidatos)"
        )


def _print_allocation(allocation: Dict[str, int], pacts: Iterable[PactResult]) -> None:
    pact_lookup = {pact.code: pact for pact in pacts}
    if not allocation:
        print("   No se asignaron escaños")
        return
    for code, seats in sorted(allocation.items(), key=lambda item: (-item[1], item[0])):
        pact = pact_lookup.get(code)
        name = pact.name if pact else "Pacto desconocido"
        votes = pact.votes if pact else 0
        print(f"   {code}: {name} -> {seats} escaños ({votes:,} votos)")


def _merge_pacts(pacts: Sequence[PactResult], codes: set[str]) -> Tuple[List[PactResult], str]:
    merged_candidates: List[CandidateResult] = []
    merged_votes = 0
    merged_names: List[str] = []
    merged_codes: List[str] = []
    result: List[PactResult] = []

    for pact in pacts:
        if pact.code.upper() in codes:
            merged_votes += pact.votes
            merged_candidates.extend(pact.candidates)
            merged_names.append(pact.name)
            merged_codes.append(pact.code)
        else:
            result.append(pact)

    if not merged_codes:
        raise ValueError(
            f"Ninguno de los pactos solicitados ({', '.join(sorted(codes))}) está presente en la circunscripción"
        )

    merged_label = " + ".join(merged_codes)
    merged_name = " + ".join(merged_names)
    merged_pact = PactResult(
        code=merged_label,
        name=merged_name,
        label=merged_label,
        votes=merged_votes,
        percentage=None,
        candidate_slots=None,
        seats_won=None,
        candidates=sorted(merged_candidates, key=lambda c: (-c.votes, c.number)),
    )
    result.append(merged_pact)
    return result, merged_label


def _record_pact_names(pact_names: Dict[str, str], pacts: Iterable[PactResult]) -> None:
    for pact in pacts:
        pact_names.setdefault(pact.code, pact.name)


@dataclass(frozen=True)
class _SubpactResult:
    code: str
    votes: int


def _winners_by_pact(pacts: Iterable[PactResult], allocation: Dict[str, int]) -> Dict[str, List[CandidateResult]]:
    winners: Dict[str, List[CandidateResult]] = {}
    pact_lookup = {pact.code: pact for pact in pacts}
    for code, seats in allocation.items():
        pact = pact_lookup.get(code)
        if not pact or seats <= 0:
            continue
        winners[code] = _select_winners_from_pact(pact, seats)
    return winners


def _select_winners_from_pact(pact: PactResult, seats: int) -> List[CandidateResult]:
    if not pact.candidates or seats <= 0:
        return []
    subpact_seats = _subpact_allocation(pact, seats)
    if not subpact_seats:
        return _top_candidates(pact.candidates, seats)

    candidates_by_subpact = _group_candidates_by_subpact(pact.candidates)
    selected: List[CandidateResult] = []
    for subpact_code, subpact_seats_count in subpact_seats.items():
        if subpact_seats_count <= 0:
            continue
        ordered = _top_candidates(candidates_by_subpact.get(subpact_code, []), subpact_seats_count)
        selected.extend(ordered)

    selected.sort(key=_candidate_sort_key)
    return selected[:seats]


def _subpact_allocation(pact: PactResult, seats: int) -> Dict[str, int]:
    if seats <= 0:
        return {}
    totals: Counter[str] = Counter()
    for candidate in pact.candidates:
        code = _candidate_subpact_code(candidate)
        if not code:
            continue
        totals[code] += max(candidate.votes, 0)

    subpacts = [
        _SubpactResult(code=code, votes=votes)
        for code, votes in totals.items()
        if votes > 0
    ]
    if not subpacts:
        return {}
    return dhondt_allocation(subpacts, seats)


def _group_candidates_by_subpact(candidates: Iterable[CandidateResult]) -> Dict[str, List[CandidateResult]]:
    grouped: Dict[str, List[CandidateResult]] = defaultdict(list)
    for candidate in candidates:
        code = _candidate_subpact_code(candidate)
        grouped[code].append(candidate)
    return grouped


def _top_candidates(candidates: Iterable[CandidateResult], seats: int) -> List[CandidateResult]:
    ordered = sorted(candidates, key=_candidate_sort_key)
    return ordered[:seats]


def _candidate_subpact_code(candidate: CandidateResult) -> str:
    if candidate.party:
        stripped = candidate.party.strip()
        if stripped:
            return stripped
    if candidate.pact_code:
        return f"{candidate.pact_code} (sin partido)"
    return "(sin partido)"


def _candidate_sort_key(candidate: CandidateResult) -> tuple[int, int, str]:
    return (-candidate.votes, candidate.number, candidate.name)


def _has_result_changes(
    original_winners: Dict[str, List[CandidateResult]],
    merged_winners: Dict[str, List[CandidateResult]],
) -> bool:
    return _winner_signature(original_winners) != _winner_signature(merged_winners)


def _winner_signature(winners: Dict[str, List[CandidateResult]]) -> Counter[tuple[str, int, str]]:
    signature: Counter[tuple[str, int, str]] = Counter()
    for candidates in winners.values():
        for candidate in candidates:
            signature[(candidate.pact_code or "", candidate.number, candidate.name)] += 1
    return signature


def _print_winners(title: str, winners: Dict[str, List[CandidateResult]]) -> None:
    print(f"\n{title}:")
    if not winners:
        print("   (sin información)")
        return
    for code, candidates in sorted(winners.items()):
        formatted = ", ".join(f"{c.name} ({c.votes:,} votos)" for c in candidates)
        print(f"   {code}: {formatted}")


def _merged_breakdown_counts(
    merged_label: str, winners: Dict[str, List[CandidateResult]]
) -> Counter[str]:
    selected = winners.get(merged_label)
    breakdown: Counter[str] = Counter()
    if not selected:
        return breakdown
    for candidate in selected:
        pact_code = candidate.pact_code or "(sin código)"
        breakdown[pact_code] += 1
    return breakdown


def _print_merged_breakdown(merged_label: str, breakdown: Counter[str]) -> None:
    if not breakdown:
        return
    print(f"      Detalle interno de {merged_label}:")
    for code, count in sorted(breakdown.items(), key=lambda item: (-item[1], item[0])):
        suffix = "escaños" if count != 1 else "escaño"
        print(f"         - {code}: {count} {suffix}")


def _distribute_allocation_by_origin(
    allocation: Dict[str, int], merged_label: str, breakdown: Counter[str]
) -> Counter[str]:
    distributed: Counter[str] = Counter()
    for code, seats in allocation.items():
        if code == merged_label and breakdown:
            distributed.update(breakdown)
        else:
            distributed[code] += seats
    return distributed


def _print_summary(
    summary_official: Counter[str],
    summary_scenario: Counter[str],
    summary_scenario_by_origin: Counter[str],
    pact_names: Dict[str, str],
    summary_breakdowns: Dict[str, Counter[str]],
) -> None:
    print("\n=== Resumen consolidado ===")
    _print_summary_block("Reparto oficial", summary_official, pact_names)
    _print_summary_block("Escenario unificado", summary_scenario, pact_names)

    print("\nVariación de escaños:")
    all_codes = sorted(set(summary_official) | set(summary_scenario_by_origin))
    for code in all_codes:
        original = summary_official.get(code, 0)
        scenario = summary_scenario_by_origin.get(code, 0)
        diff = scenario - original
        sign = "+" if diff > 0 else ""
        label = _format_pact_label(code, pact_names)
        print(f"   {label}: {original} -> {scenario} ({sign}{diff})")


def _print_summary_block(title: str, data: Counter[str], pact_names: Dict[str, str]) -> None:
    print(f"\n{title}:")
    if not data:
        print("   (sin datos)")
        return
    for code, seats in sorted(data.items(), key=lambda item: (-item[1], item[0])):
        label = _format_pact_label(code, pact_names)
        print(f"   {label}: {seats} escaños")


def _format_pact_label(code: str, pact_names: Dict[str, str]) -> str:
    name = pact_names.get(code)
    if name and name != code:
        return f"{code} ({name})"
    return code


if __name__ == "__main__":
    main()
