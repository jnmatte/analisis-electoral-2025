"""Lectura y normalización de los resultados electorales desde Excel."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List

import pandas as pd


@dataclass
class CandidateResult:
    """Resultado individual de una candidatura."""

    number: int
    name: str
    party: str | None
    votes: int
    percentage: float | None
    elected: bool
    pact_code: str | None = None


@dataclass
class PactResult:
    """Resultado agregado para un pacto/lista dentro de una circunscripción."""

    code: str
    name: str
    label: str
    votes: int
    percentage: float | None
    candidate_slots: int | None
    seats_won: int | None
    candidates: List[CandidateResult] = field(default_factory=list)


@dataclass
class CircunscripcionResult:
    """Resultados de una circunscripción senatorial o distrito de diputados."""

    circunscripcion_id: str
    circunscripcion_label: str
    seats: int
    pacts: List[PactResult]


SUMMARY_PREFIXES = (
    "válidamente",
    "votos nulos",
    "votos en blanco",
    "total votación",
    "resultados preliminares",
)


def load_circunscripciones(inputs_dir: Path | str) -> List[CircunscripcionResult]:
    """Carga todas las circunscripciones disponibles en ``inputs_dir``."""

    directory = Path(inputs_dir)
    if not directory.exists():
        raise FileNotFoundError(f"No se encontró la carpeta {directory}")

    circunscripciones: List[CircunscripcionResult] = []
    for path in sorted(directory.glob("*.xlsx")):
        circunscripciones.append(_parse_file(path))
    if not circunscripciones:
        raise ValueError(f"No se encontraron archivos Excel en {directory}")
    return circunscripciones


def _parse_file(path: Path) -> CircunscripcionResult:
    df = pd.read_excel(path, header=10)
    seats = _extract_seats(path)
    circ_id, circ_label = _extract_circunscripcion_metadata(path)

    pacts: List[PactResult] = []
    current_pact: PactResult | None = None
    for _, row in df.iterrows():
        raw_label = row.get("Lista/Pacto")
        if isinstance(raw_label, str) and raw_label.strip():
            label = raw_label.strip()
            if _is_summary_row(label):
                break
            current_pact = _build_pact(label, row)
            pacts.append(current_pact)
            continue

        if current_pact is None:
            # Todavía no llegamos a la primera lista.
            continue

        candidate_field = row.get("Unnamed: 1")
        if isinstance(candidate_field, str) and candidate_field.strip():
            candidate = _build_candidate(candidate_field, row, current_pact.code)
            current_pact.candidates.append(candidate)

    return CircunscripcionResult(
        circunscripcion_id=circ_id,
        circunscripcion_label=circ_label,
        seats=seats,
        pacts=pacts,
    )


def _extract_seats(path: Path) -> int:
    df = pd.read_excel(path, header=None)
    for value in df.iloc[:, 0].dropna():
        if not isinstance(value, str):
            continue
        value_lower = value.lower()
        match = re.search(r"(\d+)\s+(senadores|diputados)\s+a\s+elegir", value_lower)
        if match:
            return int(match.group(1))
        generic_match = re.search(r"(\d+)", value_lower)
        if generic_match and ("senadores" in value_lower or "diputados" in value_lower):
            return int(generic_match.group(1))
    raise ValueError(f"No pude determinar el número de escaños para {path}")


def _extract_circunscripcion_metadata(path: Path) -> tuple[str, str]:
    name = path.name.upper()
    senate_match = re.search(r"CIRCUNSCRIPCIÓN SENATORIAL\s*(\d+)", name)
    if senate_match:
        circ_id = senate_match.group(1)
        return circ_id, f"Circunscripción Senatorial {circ_id}"

    district_match = re.search(r"DISTRITO\s*(\d+)", name)
    if district_match:
        circ_id = district_match.group(1)
        return circ_id, f"Distrito {circ_id}"

    circ_id = path.stem
    return circ_id, circ_id


def _is_summary_row(value: str) -> bool:
    value_lower = value.strip().lower()
    return any(value_lower.startswith(prefix) for prefix in SUMMARY_PREFIXES)


def _build_pact(label: str, row: pd.Series) -> PactResult:
    if " - " in label:
        code, name = [part.strip() for part in label.split(" - ", 1)]
    else:
        code, name = label.strip(), label.strip()

    return PactResult(
        code=code,
        name=name,
        label=label,
        votes=_parse_int(row.get("Votos")),
        percentage=_parse_percentage(row.get("Porcentaje")),
        candidate_slots=_parse_int(row.get("Candidatos")),
        seats_won=_parse_int(row.get("Electos")),
    )


def _build_candidate(raw_value: str, row: pd.Series, pact_code: str) -> CandidateResult:
    match = re.match(r"(\d+)\s+(.*)", raw_value.strip())
    if match:
        number = int(match.group(1))
        name = match.group(2).strip()
    else:
        number = 0
        name = raw_value.strip()

    electos_raw = row.get("Electos")
    elected = isinstance(electos_raw, str) and "✓" in electos_raw

    return CandidateResult(
        number=number,
        name=name,
        party=_parse_str(row.get("Partido")),
        votes=_parse_int(row.get("Votos")),
        percentage=_parse_percentage(row.get("Porcentaje")),
        elected=elected,
        pact_code=pact_code,
    )


def _parse_int(value) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^0-9]", "", value)
        return int(digits) if digits else 0
    return int(value)


def _parse_percentage(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        clean = value.strip().replace("%", "").replace(".", "").replace(",", ".")
        clean = clean.replace(" ", "")
        return float(clean) / 100 if clean else None
    return None


def _parse_str(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "CandidateResult",
    "PactResult",
    "CircunscripcionResult",
    "load_circunscripciones",
]
