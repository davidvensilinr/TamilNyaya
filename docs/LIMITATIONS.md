# LIMITATIONS.md — TamilNyaya-Bench

## Known Limitations

This document transparently lists all known limitations of TamilNyaya-Bench.
University reviewers and project guides should read this alongside the results.

---

### 1. Knowledge Base Coverage

- **Partial ingestion:** Only 25 sections from 5 Acts are currently ingested.
  Real Indian law comprises thousands of Acts with tens of thousands of sections.
- **Coverage ranges from 2.9% to 75.0%** per Act. When the system reports
  "section not found in KB", it may mean the section exists in the real Act but
  was not ingested, not that the model fabricated it.
- **The coverage table in the UI** shows ingested vs. declared sections per Act.
  All unverifiable citations due to incomplete coverage are labeled
  `UnverifiableCitation` and excluded from accuracy calculations.

### 2. Tamil Text Authenticity

- The Tamil legal text was manually prepared from publicly available Act
  structures and official gazette publications.
- While the text follows real Act content, it has not been diff-verified against
  official OCR or scanned copies of the Tamil Nadu Gazette.
- The `source_url` fields point to real government URLs, but the content was
  not fetched programmatically from those URLs (automated access timed out).
- See `docs/DATA_PROVENANCE.md` for full details.

### 3. Model Limitations

- **All evaluated models are general-purpose models** hosted on Groq's free tier.
  None are fine-tuned for Tamil legal text.
- **Groq free-tier rate limits** (20 RPM default) mean evaluation runs are slow.
  A full 147-item evaluation takes approximately 8 minutes.
- **No Tamil-specific LLM** is currently available in the system. The
  `ModelAdapter` interface exists for future integration of fine-tuned models.
- **Model outputs are non-deterministic** even with `temperature=0.0` due to
  hardware-level floating point variations.

### 4. Evaluation Methodology

- **Layer 1 (Citation Verification)** is deterministic and reliable, but its
  accuracy depends on KB coverage. Low coverage → many `UnverifiableCitation`
  verdicts → wider confidence intervals.
- **Layer 2 (NLI Faithfulness)** uses the same model family being evaluated,
  creating a potential same-model bias. The NLI model may share the same
  hallucination patterns as the model under test.
- **Layer 3 (LLM Judge)** is not yet implemented in the pipeline runner.
  Judge verdicts require human calibration (Cohen's κ ≥ 0.6) before they
  contribute to aggregated scores.
- **Bootstrap confidence intervals** are meaningful only with sufficient sample
  sizes. With 147 items, CIs will be wide.

### 5. Annotation and Calibration

- **No human annotations exist yet.** The calibration dashboard will show
  "insufficient data" for all categories until real annotators label items.
- **Minimum 30 labels per category** are required before Cohen's κ is meaningful.
- **No inter-annotator agreement** can be computed with fewer than 2 annotators
  per item.

### 6. Infrastructure

- **No Docker support.** The app runs as separate Python (FastAPI) and Node.js
  (Next.js) processes.
- **SQLite** is used for simplicity but is not suitable for concurrent multi-user
  production deployment.
- **No authentication or authorization** is implemented. The app is designed for
  local research use.

### 7. Scope

- **This is a benchmark, not a legal tool.** It should not be used for legal
  advice, case research, or any purpose requiring authoritative legal information.
- **Indian law only.** Specifically Indian Central Acts and Tamil Nadu State Acts.
- **Tamil language only** for the primary evaluation language, with English
  translations where available from the source.

---

## What This Benchmark Does Well

Despite these limitations, the benchmark provides:
1. **Full traceability** — every number can be traced to its source
2. **Honest empty states** — never shows fabricated results
3. **Deterministic verification** — Layer 1 citation checking requires no LLM
4. **Auditable pipeline** — every step is logged in the audit trail
5. **Extensible design** — new Acts, models, and verification layers can be added
