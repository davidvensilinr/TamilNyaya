"""
severity.py — Severity tiers and taxonomy mappings.

Re-exports and helper utilities for the error taxonomy.
"""

from __future__ import annotations

from .taxonomy import (
    TAXONOMY,
    TAXONOMY_VERSION,
    ErrorCategory,
    ErrorGroup,
    TaxonomyEntry,
    get_entry,
    get_severity,
)

__all__ = [
    "TAXONOMY",
    "TAXONOMY_VERSION",
    "ErrorCategory",
    "ErrorGroup",
    "TaxonomyEntry",
    "get_entry",
    "get_severity",
]
