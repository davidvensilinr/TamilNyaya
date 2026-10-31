"""
taxonomy.py — Error taxonomy and severity definitions.

This is the single source of truth for all error categories and their
severity levels.  Every flagged error in the UI shows which rule assigned
its severity, referencing this module by name and version.

VERSION: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


TAXONOMY_VERSION = "1.0.0"


class ErrorGroup(str, Enum):
    FAITHFULNESS = "faithfulness"
    FACTUALITY = "factuality"


class ErrorCategory(str, Enum):
    # Faithfulness errors (usually Layer 1 or Layer 2)
    CITATION_FABRICATION = "CitationFabrication"
    SECTION_MISATTRIBUTION = "SectionMisattribution"
    CONTEXT_CONTRADICTION = "ContextContradiction"
    UNSUPPORTED_ELABORATION = "UnsupportedElaboration"
    JURISDICTION_CONFLATION = "JurisdictionConflation"

    # Factuality errors (Layer 1 or Layer 3)
    OBSOLETE_LAW_AS_CURRENT = "ObsoleteLawAsCurrent"
    WRONG_LEGAL_CONSEQUENCE = "WrongLegalConsequence"
    TERMINOLOGY_MISTRANSLATION = "TerminologyMistranslation"
    INVENTED_PRECEDENT = "InventedPrecedent"

    # Unresolvable — not an error, just outside KB coverage
    UNVERIFIABLE_CITATION = "UnverifiableCitation"


@dataclass(frozen=True)
class TaxonomyEntry:
    category: ErrorCategory
    group: ErrorGroup
    severity: int           # 1, 2, or 3
    severity_label: str     # cosmetic | misleading | dangerous
    description: str
    layer: str              # "L1" | "L2" | "L3" | "L1_or_L3"
    rule_reference: str     # e.g. "taxonomy.py v1.0.0 – CitationFabrication"


TAXONOMY: dict[ErrorCategory, TaxonomyEntry] = {
    ErrorCategory.CITATION_FABRICATION: TaxonomyEntry(
        category=ErrorCategory.CITATION_FABRICATION,
        group=ErrorGroup.FAITHFULNESS,
        severity=3,
        severity_label="dangerous",
        description=(
            "The model cited an Act and section number that do not exist, "
            "where the KB has complete section coverage for that Act. "
            "Honesty note: only the complete-coverage case may be labelled "
            "fabrication; incomplete coverage yields UnverifiableCitation."
        ),
        layer="L1",
        rule_reference="taxonomy.py v1.0.0 – CitationFabrication",
    ),
    ErrorCategory.SECTION_MISATTRIBUTION: TaxonomyEntry(
        category=ErrorCategory.SECTION_MISATTRIBUTION,
        group=ErrorGroup.FAITHFULNESS,
        severity=2,
        severity_label="misleading",
        description=(
            "The section number exists but belongs to a different Act than "
            "the one the model named."
        ),
        layer="L1",
        rule_reference="taxonomy.py v1.0.0 – SectionMisattribution",
    ),
    ErrorCategory.CONTEXT_CONTRADICTION: TaxonomyEntry(
        category=ErrorCategory.CONTEXT_CONTRADICTION,
        group=ErrorGroup.FAITHFULNESS,
        severity=2,
        severity_label="misleading",
        description=(
            "An atomic claim in the model answer is contradicted by the "
            "real source passage (NLI label: contradicted)."
        ),
        layer="L2",
        rule_reference="taxonomy.py v1.0.0 – ContextContradiction",
    ),
    ErrorCategory.UNSUPPORTED_ELABORATION: TaxonomyEntry(
        category=ErrorCategory.UNSUPPORTED_ELABORATION,
        group=ErrorGroup.FAITHFULNESS,
        severity=2,
        severity_label="misleading",
        description=(
            "An atomic claim is neither entailed nor contradicted by the "
            "source passage — the model added information the source does "
            "not support (NLI label: neutral)."
        ),
        layer="L2",
        rule_reference="taxonomy.py v1.0.0 – UnsupportedElaboration",
    ),
    ErrorCategory.JURISDICTION_CONFLATION: TaxonomyEntry(
        category=ErrorCategory.JURISDICTION_CONFLATION,
        group=ErrorGroup.FAITHFULNESS,
        severity=3,
        severity_label="dangerous",
        description=(
            "The model cited a real provision but from the wrong jurisdiction "
            "(e.g., a Central Act instead of a Tamil Nadu Act or vice versa). "
            "Severity-3 because it can cause a person to rely on law that "
            "does not apply to them."
        ),
        layer="L1",
        rule_reference="taxonomy.py v1.0.0 – JurisdictionConflation",
    ),
    ErrorCategory.OBSOLETE_LAW_AS_CURRENT: TaxonomyEntry(
        category=ErrorCategory.OBSOLETE_LAW_AS_CURRENT,
        group=ErrorGroup.FACTUALITY,
        severity=3,
        severity_label="dangerous",
        description=(
            "The model presented a repealed or superseded provision as "
            "currently in force."
        ),
        layer="L1",
        rule_reference="taxonomy.py v1.0.0 – ObsoleteLawAsCurrent",
    ),
    ErrorCategory.WRONG_LEGAL_CONSEQUENCE: TaxonomyEntry(
        category=ErrorCategory.WRONG_LEGAL_CONSEQUENCE,
        group=ErrorGroup.FACTUALITY,
        severity=3,
        severity_label="dangerous",
        description=(
            "The model stated an incorrect penalty, procedure, or legal right "
            "for the cited provision. Judged by Layer 3 (LLM judge) because "
            "it requires semantic understanding, not just a DB lookup."
        ),
        layer="L3",
        rule_reference="taxonomy.py v1.0.0 – WrongLegalConsequence",
    ),
    ErrorCategory.TERMINOLOGY_MISTRANSLATION: TaxonomyEntry(
        category=ErrorCategory.TERMINOLOGY_MISTRANSLATION,
        group=ErrorGroup.FACTUALITY,
        severity=1,
        severity_label="cosmetic",
        description=(
            "A Tamil legal term was used with the wrong meaning or mistranslated, "
            "but in a way that does not materially change the legal outcome."
        ),
        layer="L3",
        rule_reference="taxonomy.py v1.0.0 – TerminologyMistranslation",
    ),
    ErrorCategory.INVENTED_PRECEDENT: TaxonomyEntry(
        category=ErrorCategory.INVENTED_PRECEDENT,
        group=ErrorGroup.FACTUALITY,
        severity=3,
        severity_label="dangerous",
        description=(
            "The model cited a court case or legal precedent that does not exist."
        ),
        layer="L3",
        rule_reference="taxonomy.py v1.0.0 – InventedPrecedent",
    ),
    ErrorCategory.UNVERIFIABLE_CITATION: TaxonomyEntry(
        category=ErrorCategory.UNVERIFIABLE_CITATION,
        group=ErrorGroup.FAITHFULNESS,
        severity=0,
        severity_label="unverifiable",
        description=(
            "The cited Act is not in the KB, or the KB does not have complete "
            "section coverage for it. This is NOT a fabrication verdict — it "
            "means the benchmark cannot decide."
        ),
        layer="L1",
        rule_reference="taxonomy.py v1.0.0 – UnverifiableCitation",
    ),
}


def get_severity(category: ErrorCategory) -> int:
    return TAXONOMY[category].severity


def get_entry(category: ErrorCategory) -> TaxonomyEntry:
    return TAXONOMY[category]
