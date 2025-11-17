"""CLI para simular la unión de pactos en el sistema D'Hondt."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import re
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
    parser.add_argument(
        "--print-all",
        action="store_true",
        help=(
            "Muestra todos los distritos aunque no cambie el resultado. Por defecto solo se "
            "imprimen los que presentan cambios."
        ),
    )
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
    national_entries: List[_NationalScenario] = []
    national_baseline_seats = 0
    national_scenario_seats = 0
    national_merged_votes = 0.0

    for circ in circunscripciones:
        if circ_filter and circ.circunscripcion_id not in circ_filter:
            continue

        original_allocation = dhondt_allocation(circ.pacts, circ.seats)
        _record_pact_names(pact_names, circ.pacts)
        try:
            merged_pacts, merged_label, merged_original_codes = _merge_pacts(
                circ.pacts, pact_codes
            )
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
        should_print = args.print_all or has_changes

        combined_original_seats = _combined_seats(original_allocation, merged_original_codes)
        merged_seats = merged_allocation.get(merged_label, 0)
        indifference_loss = _indifference_loss_percentage(
            merged_pacts,
            merged_label,
            circ.seats,
            combined_original_seats,
            merged_seats,
        )
        national_entries.append(
            _NationalScenario(
                merged_pacts=tuple(merged_pacts),
                merged_label=merged_label,
                seats=circ.seats,
            )
        )
        national_baseline_seats += combined_original_seats
        national_scenario_seats += merged_seats

        merged_breakdown = _merged_breakdown_counts(merged_label, merged_winners)
        if merged_breakdown:
            summary_breakdowns[merged_label].update(merged_breakdown)

        summary_official.update(original_allocation)
        summary_scenario.update(merged_allocation)
        distributed_allocation = _distribute_allocation_by_origin(
            merged_allocation, merged_label, merged_breakdown
        )
        summary_scenario_by_origin.update(distributed_allocation)
        merged_votes = _pact_votes(merged_pacts, merged_label)
        if merged_votes:
            national_merged_votes += merged_votes

        if not should_print:
            continue

        print(f"\n=== {circ.circunscripcion_label} ({circ.seats} escaños) ===")
        _print_pact_table(circ.pacts)

        print("\n> Resultado oficial con los pactos originales:")
        _print_allocation(original_allocation, circ.pacts)

        print("\n> Escenario si se unen {0}:".format(" + ".join(sorted(pact_codes))))
        _print_allocation(merged_allocation, merged_pacts)

        _print_indifference_loss(indifference_loss, merged_votes)

        _print_winners("Electos oficiales", original_winners)
        _print_winners("Electos en el escenario", merged_winners)
        _print_merged_breakdown(merged_label, merged_breakdown)

        if not has_changes:
            print("\n   No hay cambios respecto al resultado oficial.")

    national_loss = _national_indifference_loss(
        national_entries, national_baseline_seats, national_scenario_seats
    )

    if processed_any:
        _print_summary(
            summary_official,
            summary_scenario,
            summary_scenario_by_origin,
            pact_names,
            summary_breakdowns,
            national_loss,
            national_merged_votes,
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


def _merge_pacts(
    pacts: Sequence[PactResult], codes: set[str]
) -> Tuple[List[PactResult], str, List[str]]:
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
    return result, merged_label, merged_codes


def _record_pact_names(pact_names: Dict[str, str], pacts: Iterable[PactResult]) -> None:
    for pact in pacts:
        pact_names.setdefault(pact.code, pact.name)


def _combined_seats(allocation: Dict[str, int], codes: Iterable[str]) -> int:
    return sum(allocation.get(code, 0) for code in codes)


@dataclass(frozen=True)
class _SubpactResult:
    code: str
    votes: int


@dataclass(frozen=True)
class _PactVotes:
    code: str
    votes: float


@dataclass(frozen=True)
class _NationalScenario:
    merged_pacts: Sequence[PactResult]
    merged_label: str
    seats: int


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
    selected_keys: set[tuple[int, int, str]] = set()
    for subpact_code, subpact_seats_count in subpact_seats.items():
        if subpact_seats_count <= 0:
            continue
        ordered = _top_candidates(candidates_by_subpact.get(subpact_code, []), subpact_seats_count)
        for candidate in ordered:
            key = _candidate_identity(candidate)
            if key in selected_keys:
                continue
            selected_keys.add(key)
            selected.append(candidate)

    if len(selected) < seats:
        remaining_needed = seats - len(selected)
        fallback_candidates = [
            candidate
            for candidate in _top_candidates(pact.candidates, len(pact.candidates))
            if _candidate_identity(candidate) not in selected_keys
        ]
        selected.extend(fallback_candidates[:remaining_needed])

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
            normalized = _normalize_independent_party_label(stripped)
            if normalized:
                return normalized
    if candidate.pact_code:
        return f"{candidate.pact_code} (sin partido)"
    return "(sin partido)"


def _normalize_independent_party_label(label: str) -> str:
    if not label:
        return label
    match = _IND_PARTY_PATTERN.match(label)
    if match:
        remainder = match.group(1).strip()
        if remainder:
            return remainder
    if label.upper() == "IND":
        return "IND"
    return label


def _candidate_sort_key(candidate: CandidateResult) -> tuple[int, int, str]:
    return (-candidate.votes, candidate.number, candidate.name)


def _candidate_identity(candidate: CandidateResult) -> tuple[int, int, str]:
    return (candidate.number, candidate.votes, candidate.name)


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


def _print_indifference_loss(indifference_loss: float, merged_votes: float | None) -> None:
    if merged_votes is None or merged_votes <= 0:
        return
    percentage = indifference_loss * 100
    lost_votes = round(merged_votes * indifference_loss)
    print(f"   Pérdida indiferente: {percentage:.2f}% (~{lost_votes:,} votos)")


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
    national_loss: float,
    national_votes: float,
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

    _print_national_indifference(national_loss, national_votes)


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


def _print_national_indifference(loss: float, total_votes: float) -> None:
    percentage = loss * 100
    print("\nPérdida indiferente nacional:")
    if percentage <= 0:
        print("   0.00%")
        return
    text = f"   {percentage:.2f}%"
    if total_votes > 0:
        lost_votes = round(total_votes * loss)
        text += f" (~{lost_votes:,} votos)"
    print(text)


def _indifference_loss_percentage(
    merged_pacts: Sequence[PactResult],
    merged_label: str,
    seats: int,
    baseline_seats: int,
    current_merged_seats: int,
) -> float:
    if current_merged_seats <= baseline_seats:
        return 0.0

    low = 0.0
    high = 1.0
    tolerance = 1e-4
    for _ in range(60):
        mid = (low + high) / 2
        scenario = _pacts_with_vote_loss(merged_pacts, merged_label, mid)
        allocation = dhondt_allocation(scenario, seats)
        seats_mid = allocation.get(merged_label, 0)
        if seats_mid > baseline_seats:
            low = mid
        else:
            high = mid
        if high - low <= tolerance:
            break
    return high


def _national_indifference_loss(
    circunscripciones: Sequence[_NationalScenario],
    baseline_total: int,
    current_total: int,
) -> float:
    if not circunscripciones or current_total <= baseline_total:
        return 0.0

    low = 0.0
    high = 1.0
    tolerance = 1e-4
    for _ in range(60):
        mid = (low + high) / 2
        total = 0
        for circ in circunscripciones:
            scenario = _pacts_with_vote_loss(circ.merged_pacts, circ.merged_label, mid)
            allocation = dhondt_allocation(scenario, circ.seats)
            total += allocation.get(circ.merged_label, 0)
        if total > baseline_total:
            low = mid
        else:
            high = mid
        if high - low <= tolerance:
            break
    return high


def _pacts_with_vote_loss(
    merged_pacts: Sequence[PactResult], merged_label: str, loss_fraction: float
) -> List[_PactVotes]:
    if not 0.0 <= loss_fraction <= 1.0:
        raise ValueError("El porcentaje de pérdida debe estar entre 0 y 100%")

    merged_votes = None
    others: List[PactResult] = []
    other_votes_total = 0.0
    for pact in merged_pacts:
        if pact.code == merged_label:
            merged_votes = float(pact.votes)
        else:
            others.append(pact)
            other_votes_total += float(pact.votes)

    if merged_votes is None:
        raise ValueError("No se encontró el pacto unificado dentro del escenario")

    loss_votes = merged_votes * loss_fraction
    new_votes = merged_votes - loss_votes
    scenario: List[_PactVotes] = [_PactVotes(code=merged_label, votes=new_votes)]

    if loss_votes <= 0 or other_votes_total <= 0:
        scenario.extend(_PactVotes(code=pact.code, votes=float(pact.votes)) for pact in others)
        return scenario

    for pact in others:
        share = float(pact.votes) / other_votes_total if other_votes_total else 0.0
        gained = loss_votes * share
        scenario.append(_PactVotes(code=pact.code, votes=float(pact.votes) + gained))
    return scenario


def _pact_votes(pacts: Sequence[PactResult], code: str) -> float | None:
    for pact in pacts:
        if pact.code == code:
            return float(pact.votes)
    return None


if __name__ == "__main__":
    main()
_IND_PARTY_PATTERN = re.compile(r"^IND\s*-\s*(.+)$", re.IGNORECASE)

