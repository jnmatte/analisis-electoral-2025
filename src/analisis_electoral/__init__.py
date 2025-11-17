"""Herramientas para simular escenarios electorales."""

from .data_loader import load_circunscripciones, CircunscripcionResult, PactResult, CandidateResult
from .dhondt import dhondt_allocation

__all__ = [
    "load_circunscripciones",
    "CircunscripcionResult",
    "PactResult",
    "CandidateResult",
    "dhondt_allocation",
]
