# TamilNyaya-Bench (தமிழ்நியாய-பெஞ்ச்)

**Auditable Benchmark Testing Small Language Models on Indian and Tamil Nadu Law**

> **Research Prototype · Not Legal Advice**  
> All evaluated models are general-purpose open models, not fine-tuned for Tamil law.

---

## 1. What It Is (and What It Is Not)

**What it is:** TamilNyaya-Bench evaluates whether small language models make up laws, section numbers, or citations when answering Tamil legal questions about Indian Central and Tamil Nadu State law. It checks model answers against a real database of official statutes and scores how often and how severely they hallucinate.

**What it is not:** It is **not** a new language model and does not train one. It is an evaluation benchmark (knowledge base + dataset + verification harness + web app).

---

## 2. Non-Negotiable Integrity Rules

1. **Zero Dummy Data:** Every number, label, legal provision, and model output is traceable to an official source document or a live computation. If data does not exist yet, the UI displays *"not available yet"* or *"not run yet"*.
2. **No Invented Legal Text:** Legal provisions are never written from AI memory. All text is parsed from official sources with cryptographic provenance (SHA-256 hashes, source URLs, raw character offsets).
3. **Traceability:** Reviewers can click any KB record or trace view to inspect the exact passage and character offsets from the raw document in `data/raw/`.
4. **Inspectable Metrics:** Every metric formula is computed on-demand from stored raw results. No precomputed or hardcoded metrics.
5. **Degraded Mode:** The system runs without an LLM API key; deterministic citation verification, KB exploration, and dataset inspection remain fully operational.

---

## 3. Architecture & Repository Structure

```
tamilnyaya-bench/
├── .env.example               # Environment template with placeholders
├── README.md                  # Setup & audit instructions
├── docs/                      # Scientific documentation
│   ├── DATA_PROVENANCE.md     # Official source documentation & coverage
│   ├── LIMITATIONS.md         # Transparent disclosure of benchmark limits
│   └── METHODOLOGY.md         # 3-layer verification & metric formulas
├── ingest/
│   ├── fetchers/              # Polite, robots.txt-aware fetchers
│   ├── manual_drop/           # Raw HTML files of official gazettes
│   ├── parsers/               # HTML parser recording version and spans
│   ├── quality/               # Data-quality report generator
│   └── run_ingest.py          # Ingestion runner script
├── data/
│   ├── raw/                   # Untouched downloaded files named by SHA-256
│   └── app.db                 # SQLite database with strict foreign keys
├── backend/app/
│   ├── main.py                # FastAPI app with graceful degraded startup
│   ├── config.py              # Pydantic v2 settings & redaction
│   ├── db.py                  # SQLAlchemy models & SQLite WAL pragmas
│   ├── audit.py               # Append-only audit logger
│   ├── integrity.py           # 7-point integrity verification script
│   ├── kb/                    # Schema, loader, coverage tracking
│   ├── items/                 # Programmatic benchmark item generator
│   ├── llm/                   # Groq client (throttled, backoff), NLI, Judge
│   ├── models_under_test/     # ModelAdapter interface & Groq adapter
│   ├── verification/          # Layer 1 citation verifier, Layer 2 NLI, taxonomy
│   ├── pipeline/              # Evaluation runner, aggregator, bootstrap CIs, ZIP bundle
│   ├── annotation/            # Human labels, Cohen's kappa agreement, adjudication
│   └── api/                   # REST routers
├── app/                       # Next.js 16 frontend (all 11 pages)
│   ├── page.tsx               # Overview dashboard
│   ├── kb/page.tsx            # Knowledge base explorer & provenance modal
│   ├── dataset/page.tsx       # Benchmark items explorer
│   ├── runs/page.tsx          # Evaluation run console
│   ├── trace/[runId]/[itemId] # Full verification trace
│   ├── leaderboard/page.tsx   # Model ranking with bootstrap CIs
│   ├── models/[modelId]/      # Model detail, category breakdown, fairness
│   ├── check/page.tsx         # Live interactive verification harness
│   ├── annotations/page.tsx   # Human annotation & judge calibration
│   ├── audit/page.tsx         # Audit log & live integrity checker
│   └── methodology/page.tsx   # Inspectable formulas & taxonomy
├── components/                # Layout, sidebar, topbar, shared UI
└── tests/                     # Unit & integration test suite
    ├── unit/                  # Verifier, taxonomy, aggregator, bootstrap, integrity
    └── integration/           # FastAPI endpoint tests
```

---

## 4. Setup Instructions

### Prerequisites
- **Python 3.11+** (Python 3.11–3.15 supported)
- **Node.js v18+** (v20+ recommended) and **npm**

### Step 1: Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure your Groq API key:
```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL_UNDER_TEST=llama-3.1-8b-instant
GROQ_MODEL_JUDGE=llama-3.3-70b-versatile
GROQ_MODEL_NLI=llama-3.1-8b-instant
GROQ_REQUESTS_PER_MINUTE=20
KAPPA_THRESHOLD=0.6
MIN_LABELED_ITEMS_FOR_CALIBRATION=30
BOOTSTRAP_RESAMPLES=2000
BOOTSTRAP_SEED=42
```
*(If `GROQ_API_KEY` is omitted, the app starts in degraded mode with LLM features disabled; all deterministic features remain active).*

---

### Step 2: Python Backend Setup

#### Windows (PowerShell):
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install backend dependencies
pip install -r backend/requirements.txt  # or install via pyproject.toml
pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy python-dotenv httpx rapidfuzz beautifulsoup4 groq python-multipart pytest pytest-asyncio
```

#### macOS / Linux:
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy python-dotenv httpx rapidfuzz beautifulsoup4 groq python-multipart pytest pytest-asyncio
```

---

### Step 3: Populate Knowledge Base & Benchmark Items

Run the official ingestion pipeline:
```bash
# Ingest raw legislation into KB (computes SHA-256 and copies to data/raw/)
python -m ingest.run_ingest

# Generate benchmark items across 5 task families
python -m backend.app.items.generator

# Verify data quality report
python -m ingest.quality.quality_report
```

---

### Step 4: Run Backend Server
```bash
# Run FastAPI server on port 8000
uvicorn backend.app.main:app --reload --port 8000
```
Interactive API docs are available at: `http://localhost:8000/api/docs`

---

### Step 5: Frontend Setup & Execution
In a new terminal:
```bash
# Install frontend dependencies
npm install

# Start Next.js development server
npm run dev
```
Open `http://localhost:3000` in your browser.

To produce an optimized production build:
```bash
npm run build
npm start
```

---

## 5. Running Verification & Integrity Tests

Run the full automated test suite:
```bash
# Execute unit and integration tests
pytest tests/ -v
```

Execute the 7-point standalone integrity checker:
```bash
python -m backend.app.integrity
```

---

## 6. Verification Pipeline Summary

| Layer | Type | Mechanism | Output |
|---|---|---|---|
| **Layer 1** | Deterministic | Regex + Tamil Digit Normalization + Fuzzy KB Match | Citation accuracy, fabrication, wrong section, repealed law, jurisdiction |
| **Layer 2** | NLI Entailment | Atomic claim splitting + LLM NLI Prompting | Faithfulness score (% claims entailed by source) |
| **Layer 3** | Calibrated Judge | Multi-aspect legal evaluation calibrated against human labels (κ ≥ 0.6) | Fuzzy hallucination detection |

---

## 7. License & Data Provenance

All Indian Central and Tamil Nadu State legislation is published by official government bodies and is in the public domain under Section 52(1)(q) of the Indian Copyright Act, 1957.
See [docs/DATA_PROVENANCE.md](docs/DATA_PROVENANCE.md) for full attribution and [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for research constraints.
