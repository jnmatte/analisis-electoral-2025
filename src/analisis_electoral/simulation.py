"""CLI para simular la unión de pactos en el sistema D'Hondt."""
from __future__ import annotations

import argparse
from collections import Counter
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
            "Simula cómo cambiaría la asignación de escaños si dos pactos senatoriales "
            "hubieran competido juntos."
        )
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        default=Path("Inputs/Senadores"),
        help="Carpeta que contiene los archivos Excel oficiales",
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
    processed_any = False

    for circ in circunscripciones:
        if circ_filter and circ.circunscripcion_id not in circ_filter:
            continue
        print(f"\n=== {circ.circunscripcion_label} ({circ.seats} escaños) ===")
        _print_pact_table(circ.pacts)

        original_allocation = dhondt_allocation(circ.pacts, circ.seats)
        try:
            merged_pacts, merged_label = _merge_pacts(circ.pacts, pact_codes)
        except ValueError as exc:
            print(f"\nNo fue posible crear el escenario: {exc}")
            continue
        merged_allocation = dhondt_allocation(merged_pacts, circ.seats)
        processed_any = True

        print("\n> Resultado oficial con los pactos originales:")
        _print_allocation(original_allocation, circ.pacts)

        print("\n> Escenario si se unen {0}:".format(" + ".join(sorted(pact_codes))))
        _print_allocation(merged_allocation, merged_pacts)

        original_winners = _winners_by_pact(circ.pacts, original_allocation)
        merged_winners = _winners_by_pact(merged_pacts, merged_allocation)

        _print_winners("Electos oficiales", original_winners)
        _print_winners("Electos en el escenario", merged_winners)
        _print_merged_breakdown(merged_label, merged_winners)

        summary_official.update(original_allocation)
        summary_scenario.update(merged_allocation)

    if processed_any:
        _print_summary(summary_official, summary_scenario)


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


def _winners_by_pact(pacts: Iterable[PactResult], allocation: Dict[str, int]) -> Dict[str, List[CandidateResult]]:
    winners: Dict[str, List[CandidateResult]] = {}
    pact_lookup = {pact.code: pact for pact in pacts}
    for code, seats in allocation.items():
        pact = pact_lookup.get(code)
        if not pact:
            continue
        if seats <= 0:
            continue
        ordered_candidates = sorted(pact.candidates, key=lambda c: (-c.votes, c.number))
        winners[code] = ordered_candidates[:seats]
    return winners


def _print_winners(title: str, winners: Dict[str, List[CandidateResult]]) -> None:
    print(f"\n{title}:")
    if not winners:
        print("   (sin información)")
        return
    for code, candidates in sorted(winners.items()):
        formatted = ", ".join(f"{c.name} ({c.votes:,} votos)" for c in candidates)
        print(f"   {code}: {formatted}")


def _print_merged_breakdown(
    merged_label: str, winners: Dict[str, List[CandidateResult]]
) -> None:
    selected = winners.get(merged_label)
    if not selected:
        return
    breakdown: Dict[str, List[CandidateResult]] = {}
    for candidate in selected:
        pact_code = candidate.pact_code or "(sin código)"
        breakdown.setdefault(pact_code, []).append(candidate)
    print(f"      Detalle interno de {merged_label}:")
    for code in sorted(breakdown):
        formatted = ", ".join(f"{c.name} ({c.votes:,} votos)" for c in breakdown[code])
        print(f"         - {code}: {formatted}")


def _print_summary(
    summary_official: Counter[str], summary_scenario: Counter[str]
) -> None:
    print("\n=== Resumen consolidado ===")
    _print_summary_block("Reparto oficial", summary_official)
    _print_summary_block("Escenario unificado", summary_scenario)

    print("\nVariación de escaños:")
    all_codes = sorted(set(summary_official) | set(summary_scenario))
    for code in all_codes:
        original = summary_official.get(code, 0)
        scenario = summary_scenario.get(code, 0)
        diff = scenario - original
        sign = "+" if diff > 0 else ""
        print(f"   {code}: {original} -> {scenario} ({sign}{diff})")


def _print_summary_block(title: str, data: Counter[str]) -> None:
    print(f"\n{title}:")
    if not data:
        print("   (sin datos)")
        return
    for code, seats in sorted(data.items(), key=lambda item: (-item[1], item[0])):
        print(f"   {code}: {seats} escaños")


if __name__ == "__main__":
    main()
