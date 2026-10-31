"""
run_ingest.py — Ingestion pipeline for TamilNyaya-Bench.

Rules:
1. Reads raw official documents from ingest/manual_drop/.
2. Computes SHA-256 hash of the untouched raw content.
3. Saves untouched raw files into data/raw/<sha256>.html.
4. Parses sections with provenance, exact character offsets, and extraction method.
5. Ingests into kb_records and updates act_coverage.
6. Enforces all integrity constraints (no duplicates, no missing provenance).
7. Logs every step and rejection to the audit log.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add workspace to sys.path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from backend.app.config import settings
from backend.app.db import create_all_tables, get_db_session, ActCoverage
from backend.app import audit as audit_mod
from backend.app.kb.loader import load_parsed_act
from ingest.parsers.html_parser import parse_indiacode_act

SOURCE_URL_MAP = {
    "tn_harassment_of_woman_1998.html": "https://www.stationeryprinting.tn.gov.in/gazette/1998/act44.pdf",
    "central_domestic_violence_2005.html": "https://www.indiacode.nic.in/handle/123456789/2017/act-43-of-2005",
    "tn_tenancy_act_2017.html": "https://www.stationeryprinting.tn.gov.in/gazette/2017/act42.pdf",
    "tn_lease_rent_control_1960.html": "https://www.stationeryprinting.tn.gov.in/gazette/1960/act18.pdf",
    "central_transfer_of_property_1882.html": "https://www.indiacode.nic.in/handle/123456789/2338/act-4-of-1882",
}

SECTIONS_DECLARED_IN_SOURCE = {
    "The Tamil Nadu Prohibition of Harassment of Woman Act, 1998": 8,
    "The Protection of Women from Domestic Violence Act, 2005": 37,
    "The Tamil Nadu Regulation of Rights and Responsibilities of Landlords and Tenants Act, 2017": 47,
    "The Tamil Nadu Buildings (Lease and Rent Control) Act, 1960": 38,
    "The Transfer of Property Act, 1882": 137,
}


def run_ingestion() -> dict:
    create_all_tables()
    manual_drop_dir = Path("ingest/manual_drop")
    raw_dir = settings.data_raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(list(manual_drop_dir.glob("*.html")))
    if not files:
        print("No HTML files found in ingest/manual_drop/")
        return {"acts_processed": 0, "total_sections_inserted": 0}

    now = datetime.now(timezone.utc)
    acts_processed = 0
    total_sections_inserted = 0

    audit_mod.log("ingest_pipeline_start", f"Starting ingestion from {manual_drop_dir}")

    for file_path in files:
        raw_bytes = file_path.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Save untouched raw file
        dest_path = raw_dir / f"{sha256}.html"
        if not dest_path.exists():
            dest_path.write_bytes(raw_bytes)

        source_url = SOURCE_URL_MAP.get(file_path.name, f"file://manual_drop/{file_path.name}")
        raw_html = raw_bytes.decode("utf-8")

        parsed = parse_indiacode_act(
            html=raw_html,
            source_url=source_url,
            source_file_sha256=sha256,
            retrieved_at=now,
        )

        load_res = load_parsed_act(parsed)
        acts_processed += 1
        total_sections_inserted += load_res.sections_inserted

        # Update declared sections in coverage if known
        declared = SECTIONS_DECLARED_IN_SOURCE.get(load_res.act_name_en)
        if declared:
            with get_db_session() as session:
                cov = session.query(ActCoverage).filter_by(act_name_en=load_res.act_name_en).first()
                if cov:
                    cov.sections_in_source = declared
                    session.commit()

        print(f"Processed: {load_res.act_name_en} -> {load_res.sections_inserted} sections inserted ({load_res.sections_rejected} rejected)")

    audit_mod.log(
        "ingest_pipeline_complete",
        f"Completed: {acts_processed} acts, {total_sections_inserted} total sections inserted into KB",
    )

    return {
        "acts_processed": acts_processed,
        "total_sections_inserted": total_sections_inserted,
    }


if __name__ == "__main__":
    res = run_ingestion()
    print(f"Ingestion finished: {res}")
