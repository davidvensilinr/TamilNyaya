"""
export_bundle.py — Export run audit bundle as a streaming zip.

The bundle contains:
- config_snapshot.json (settings, no API key)
- dataset.jsonl        (all items in the run)
- kb_hashes.json       (SHA-256 of every source file referenced)
- raw_responses.jsonl  (all verbatim model outputs)
- verification_traces.jsonl (all layer 1/2/3 results)
- README.txt           (how to verify the bundle)
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Generator

from ..db import EvalRun, RunResult, BenchmarkItem, KBRecord, get_db_session


def build_bundle_stream(run_id: str) -> Generator[bytes, None, None]:
    """Stream a zip file for the given run."""
    with get_db_session() as session:
        run = session.query(EvalRun).filter_by(run_id=run_id).first()
        if not run:
            raise ValueError(f"Run '{run_id}' not found")

        results = session.query(RunResult).filter_by(run_id=run_id).all()
        item_ids = [r.item_id for r in results]
        items = session.query(BenchmarkItem).filter(BenchmarkItem.item_id.in_(item_ids)).all()

        # Gather source file SHA-256 values
        record_ids = {i.primary_source_record_id for i in items}
        kb_records = session.query(KBRecord).filter(KBRecord.record_id.in_(record_ids)).all()
        kb_hashes = {
            r.record_id: {
                "sha256": r.source_file_sha256,
                "source_url": r.source_url,
                "retrieved_at": r.retrieved_at.isoformat(),
            }
            for r in kb_records
        }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Config snapshot
        config = json.loads(run.config_snapshot) if run.config_snapshot else {}
        zf.writestr("config_snapshot.json", json.dumps(config, indent=2))

        # Dataset
        dataset_lines = "\n".join(
            json.dumps({
                "item_id": i.item_id,
                "task_family": i.task_family,
                "template_name": i.template_name,
                "gold_answer": i.gold_answer,
                "gold_status": i.gold_status,
                "jurisdiction": i.jurisdiction,
                "topic_tag": i.topic_tag,
                "is_adversarial": i.is_adversarial,
                "primary_source_record_id": i.primary_source_record_id,
            })
            for i in items
        )
        zf.writestr("dataset.jsonl", dataset_lines)

        # KB hashes
        zf.writestr("kb_hashes.json", json.dumps(kb_hashes, indent=2))

        # Raw responses
        raw_lines = "\n".join(
            json.dumps({
                "run_id": r.run_id,
                "item_id": r.item_id,
                "timestamp": r.timestamp.isoformat(),
                "raw_response": r.raw_response,
                "user_prompt": r.user_prompt,
                "latency_ms": r.latency_ms,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "http_status": r.http_status,
                "retry_count": r.retry_count,
                "error_message": r.error_message,
            })
            for r in results
        )
        zf.writestr("raw_responses.jsonl", raw_lines)

        # Verification traces
        trace_lines = "\n".join(
            json.dumps({
                "run_id": r.run_id,
                "item_id": r.item_id,
                "layer1": json.loads(r.layer1_result) if r.layer1_result else None,
                "layer2": json.loads(r.layer2_result) if r.layer2_result else None,
                "layer3": json.loads(r.layer3_result) if r.layer3_result else None,
                "error_categories": json.loads(r.error_categories) if r.error_categories else [],
                "max_severity": r.max_severity,
            })
            for r in results
        )
        zf.writestr("verification_traces.jsonl", trace_lines)

        # README
        readme = (
            f"TamilNyaya-Bench Audit Bundle\n"
            f"Run ID: {run_id}\n"
            f"Model: {run.model_id}\n"
            f"Provider: {run.provider}\n"
            f"Started: {run.started_at.isoformat()}\n"
            f"Completed: {run.completed_at.isoformat() if run.completed_at else 'not complete'}\n\n"
            "Contents:\n"
            "  config_snapshot.json  — all settings used (API key redacted)\n"
            "  dataset.jsonl         — benchmark items evaluated\n"
            "  kb_hashes.json        — SHA-256 of every source document referenced\n"
            "  raw_responses.jsonl   — verbatim model outputs, never edited\n"
            "  verification_traces.jsonl — layer 1/2/3 results per item\n\n"
            "To verify KB record provenance:\n"
            "  1. Find the record_id in dataset.jsonl\n"
            "  2. Look up kb_hashes.json for its sha256 and source_url\n"
            "  3. The raw file is in data/raw/<sha256>.html in the repository\n"
            "  4. Compare the sha256: sha256sum data/raw/<sha256>.html\n\n"
            "Research prototype. Not legal advice.\n"
            "Evaluated models are general-purpose, not fine-tuned for Tamil law.\n"
        )
        zf.writestr("README.txt", readme)

    yield buf.getvalue()
