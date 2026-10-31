# METHODOLOGY.md — TamilNyaya-Bench

## Overview

TamilNyaya-Bench evaluates whether small language models hallucinate when
answering Tamil legal questions about Indian and Tamil Nadu law. It does this by:

1. Building a knowledge base of real legal provisions from official sources
2. Generating benchmark items programmatically from those real provisions
3. Collecting model responses via the Groq API
4. Verifying responses through a three-layer verification pipeline
5. Aggregating results with bootstrap confidence intervals

---

## Knowledge Base Construction

### Sources
- India Code (indiacode.nic.in) for Central Acts
- Tamil Nadu Government Gazette for State Acts
- See `docs/DATA_PROVENANCE.md` for complete source documentation

### Schema
Every KB record carries mandatory provenance:
- `source_url`, `source_file_sha256`, `retrieved_at`
- `parser_name_and_version`, `extraction_method`
- `raw_span` (character offsets in the source file)
- `jurisdiction` (Central | Tamil Nadu) — taken from source, never inferred
- `in_force` — null if source does not state it

### Coverage Tracking
For each Act, the system tracks sections_ingested vs. sections_in_source.
Verification results account for incomplete coverage: a citation to a section
outside KB coverage is labeled `UnverifiableCitation`, not `CitationFabrication`.

---

## Benchmark Item Generation

Items are generated programmatically from real KB records using documented
templates. Each item records its generator script, template name/version,
source record IDs, and how the gold answer was derived.

### Task Families

| Family | Description | Gold Answer Source |
|--------|-------------|-------------------|
| `citation_completion` | Show real section text → identify Act and section | KB record's act_name and section_no |
| `grounded_qa` | Give real text as context → answer from it | Extractive span from real text_ta |
| `closed_book_legal_qa` | Ask about a provision without context | KB record's full provenance |
| `jurisdiction_probe` | Paired Central/TN provisions on same topic | KB record's jurisdiction field |
| `adversarial` | Perturbations: wrong Act, repealed law, flipped jurisdiction | Perturbation metadata from real records |

### Adversarial Perturbation Types

1. **Wrong Act** (`adversarial_wrong_act_v1`): Real section text attributed to a
   different real Act. Tests whether the model recognizes the mismatch.
2. **Repealed Provision** (`adversarial_repealed_v1`): Text from a repealed Act
   presented as current law. Tests temporal awareness.
3. **Flipped Jurisdiction** (`adversarial_flipped_jurisdiction_v1`): Central
   provision presented as Tamil Nadu or vice versa. Tests jurisdiction awareness.

---

## Three-Layer Verification Pipeline

### Layer 1: Deterministic Citation Verification

**No LLM required.** Pure regex + fuzzy matching.

```
citation_accuracy = correct_citations / total_verifiable_citations
```

Steps:
1. Extract citations from model response using regex patterns for:
   - "Section X of Act Y"
   - "Act Y, Section X"
   - Tamil patterns: "பிரிவு X", "சட்டம் Y"
   - Tamil digit conversion (௧௨௩ → 123)
2. Normalize extracted citations
3. Look up each citation in the KB using:
   - Exact match on section_no + act_name
   - Fuzzy match (rapidfuzz, threshold 80) on act_name
4. Check jurisdiction consistency if required
5. Check in_force status
6. Assign verdict from error taxonomy

**Verdict categories:**
- `CORRECT` — citation verified against KB
- `CitationFabrication` (severity 3) — Act+section not found in KB, and KB has
  complete coverage for that Act
- `WrongSection` (severity 2) — Act found but section doesn't exist
- `JurisdictionConflation` (severity 3) — citation found but wrong jurisdiction
- `ObsoleteLawAsCurrent` (severity 3) — citing a repealed provision as current
- `UnverifiableCitation` (severity 0) — cannot verify due to incomplete KB coverage

### Layer 2: NLI Faithfulness Scoring

**Requires LLM.** Uses the configured NLI model (default: llama-3.1-8b-instant).

```
faithfulness_score = entailed_claims / total_claims
```

Steps:
1. Split model answer into atomic claims
2. For each claim, prompt the NLI model:
   "Given: [source passage]. Claim: [claim]. Is this ENTAILED, NEUTRAL, or CONTRADICTED?"
3. Count entailed, neutral, and contradicted claims
4. Compute faithfulness as entailed / total

**Applicable to:** grounded_qa and citation_completion items (where a source
passage is available).

### Layer 3: LLM Judge (Not Yet Active in Pipeline)

**Requires LLM + human calibration.** Uses a stronger judge model
(default: llama-3.3-70b-versatile).

For fuzzy error categories that cannot be verified deterministically, the judge
model provides a second opinion. Judge verdicts are:
- **Suppressed** if Cohen's κ with human annotators < threshold (default 0.6)
- **Flagged** as "human review required" if κ is below threshold
- **Included** in aggregated scores only when calibrated

---

## Metrics and Aggregation

All metrics are computed on demand from stored raw results. No precomputed or
cached values. Each metric has an explanation endpoint: `GET /api/metrics/{name}/explain`.

### Primary Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Citation Accuracy | `correct / total_verifiable` | Fraction of verifiable citations that are correct |
| Severity-3 Rate | `count(severity=3) / total_items` | Fraction of items with critical hallucination |
| Faithfulness Score | `entailed / total_claims` | Mean fraction of claims supported by source |
| Jurisdiction Confusion | `JurisdictionConflation / jurisdiction_probes` | How often Central/TN are confused |
| Adversarial Δ | `accuracy_clean - accuracy_adversarial` | Drop under adversarial perturbations |

### Confidence Intervals

Bootstrap confidence intervals (95%) are computed for citation_accuracy and
severity3_rate:
- Default: 2000 resamples, seed 42
- Method: percentile bootstrap on per-item scores

### Fairness Gaps

Metrics are disaggregated by jurisdiction (Central vs Tamil Nadu) to detect
systematic performance differences.

---

## Error Taxonomy

Version: 1.0.0

### Severity Levels
- **Severity 1 (Minor):** UnsupportedElaboration, TerminologyMistranslation,
  MinorOmission, ProceduralImprecision
- **Severity 2 (Moderate):** WrongSection, PartialHallucination
- **Severity 3 (Critical):** CitationFabrication, JurisdictionConflation,
  ObsoleteLawAsCurrent, WrongLegalConsequence, InventedPrecedent

### Taxonomy Groups
- **Faithfulness:** errors about the relationship between source text and model output
- **Factuality:** errors about verifiable facts (Act names, section numbers, legal status)

---

## Human Annotation and Calibration

### Workflow
1. Annotators label items with error categories and severity via the Annotation page
2. Multiple annotators per item enable inter-annotator agreement (Cohen's κ)
3. Disagreements are resolved through adjudication
4. LLM judge verdicts for fuzzy categories are calibrated against human labels

### Calibration Requirements
- Minimum 30 labeled items per error category
- Cohen's κ ≥ 0.6 required for a category to be considered "calibrated"
- Below threshold: judge verdicts are flagged "human review required"

---

## Reproducibility

- **Deterministic seeds:** Bootstrap seed (42), item generation seed (42)
- **Config snapshot:** Every evaluation run stores a JSON snapshot of all settings
- **Dataset hash:** SHA-256 hash of the items used in each run
- **KB hash:** SHA-256 hash of the KB state at run time
- **Export bundle:** Full audit bundle (ZIP) downloadable per run, containing
  all inputs, outputs, and verification results
- **Audit log:** Every action logged with timestamp, action type, and detail
