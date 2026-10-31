"""
generator.py — Programmatic benchmark item generator.

Creates benchmark items from REAL KB records using documented templates.
Each item records: generator script, template name/version, source record IDs,
and how the gold answer was derived.

GENERATOR SCRIPT: backend/app/items/generator.py
TEMPLATE VERSION: 1.0.0

Rules (Part 1):
- NO invented legal text, Act names, sections, or Tamil translations.
- Gold answers are ALWAYS derived from real KB records.
- grounded_qa gold answers are extractive spans from real text (never generated).
- Each item links to its source record(s) for full traceability.
"""

from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..db import KBRecord, BenchmarkItem, get_db_session, create_all_tables
from .. import audit as audit_mod

GENERATOR_SCRIPT = "backend/app/items/generator.py"
TEMPLATE_VERSION = "1.0.0"


@dataclass
class GenerationResult:
    total_generated: int = 0
    by_family: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def generate_all_items(seed: int = 42) -> GenerationResult:
    """
    Generate benchmark items from all real KB records.
    Idempotent: skips items whose (template_name, primary_source_record_id)
    already exist.
    """
    create_all_tables()
    rng = random.Random(seed)
    result = GenerationResult()

    with get_db_session() as session:
        records = session.query(KBRecord).all()

    if not records:
        result.errors.append("No KB records found. Run ingestion first.")
        return result

    audit_mod.log(
        "item_generation_start",
        f"Starting item generation from {len(records)} KB records, seed={seed}",
    )

    # Group records by jurisdiction and act
    by_jurisdiction: dict[str, list[KBRecord]] = {}
    by_act: dict[str, list[KBRecord]] = {}
    for r in records:
        by_jurisdiction.setdefault(r.jurisdiction, []).append(r)
        by_act.setdefault(r.act_name_en, []).append(r)

    # 1. Citation completion — one per record
    for r in records:
        _create_citation_completion(r, result)

    # 2. Grounded QA — one per record (if text_ta is not empty)
    for r in records:
        if r.text_ta and r.text_ta.strip():
            _create_grounded_qa(r, result)

    # 3. Closed-book legal QA — one per record
    for r in records:
        _create_closed_book_qa(r, result)

    # 4. Jurisdiction probe — pair Central vs Tamil Nadu on related subjects
    _create_jurisdiction_probes(by_jurisdiction, by_act, result)

    # 5. Adversarial — perturbations of real records
    _create_adversarial_items(records, by_act, rng, result)

    audit_mod.log(
        "item_generation_complete",
        f"Generated {result.total_generated} items: {json.dumps(result.by_family)}. "
        f"Skipped {len(result.skipped)}, errors {len(result.errors)}.",
    )

    return result


def _item_exists(template_name: str, record_id: str) -> bool:
    """Check if an item with this template+record already exists."""
    with get_db_session() as session:
        return (
            session.query(BenchmarkItem)
            .filter_by(template_name=template_name, primary_source_record_id=record_id)
            .first()
            is not None
        )


def _insert_item(item: BenchmarkItem, result: GenerationResult) -> None:
    family = item.task_family  # read before session detaches
    with get_db_session() as session:
        session.add(item)
        session.commit()
    result.total_generated += 1
    result.by_family[family] = result.by_family.get(family, 0) + 1


def _derive_topic_tag(record: KBRecord) -> str:
    """Derive topic tag from the act name."""
    name = record.act_name_en.lower()
    if "domestic violence" in name or "harassment" in name:
        return "women_protection"
    elif "transfer of property" in name or "tenancy" in name or "lease" in name or "rent" in name:
        return "property_law"
    else:
        return "general"


# ── Template 1: Citation Completion ──────────────────────────────────────────

def _create_citation_completion(record: KBRecord, result: GenerationResult) -> None:
    template = "citation_completion_v1"
    if _item_exists(template, record.record_id):
        result.skipped.append(f"{template}:{record.record_id}")
        return

    gold = json.dumps({
        "act_name_en": record.act_name_en,
        "act_name_ta": record.act_name_ta,
        "section_no": record.section_no,
    })
    derivation = (
        f"Gold answer derived from KB record {record.record_id}: "
        f"Act='{record.act_name_en}', Section={record.section_no}. "
        f"The text shown is the real Tamil text of this section."
    )

    item = BenchmarkItem(
        item_id=str(uuid.uuid4()),
        task_family="citation_completion",
        template_name=template,
        template_version=TEMPLATE_VERSION,
        generator_script=GENERATOR_SCRIPT,
        primary_source_record_id=record.record_id,
        all_source_record_ids=json.dumps([record.record_id]),
        gold_answer=gold,
        gold_derivation=derivation,
        gold_status="derived",
        jurisdiction=record.jurisdiction,
        topic_tag=_derive_topic_tag(record),
        is_adversarial=False,
        created_at=datetime.now(timezone.utc),
    )
    _insert_item(item, result)


# ── Template 2: Grounded QA ─────────────────────────────────────────────────

def _create_grounded_qa(record: KBRecord, result: GenerationResult) -> None:
    template = "grounded_qa_v1"
    if _item_exists(template, record.record_id):
        result.skipped.append(f"{template}:{record.record_id}")
        return

    # Gold answer is an extractive span from the real text — NEVER generated
    text = record.text_ta.strip()
    # Use first meaningful sentence as extractive answer
    # Split on Tamil sentence-ending punctuation or period
    sentences = [s.strip() for s in text.replace(".", ".⌁").split("⌁") if s.strip()]
    if not sentences:
        result.errors.append(f"No sentences extractable from record {record.record_id}")
        return

    # Pick the first substantive sentence (skip very short ones)
    extractive_span = sentences[0]
    for s in sentences:
        if len(s) > 20:
            extractive_span = s
            break

    # The question is about what this provision establishes
    question = (
        f"Read the following provision from {record.act_name_en}, "
        f"Section {record.section_no} and answer: What does this section provide?"
    )

    gold = json.dumps({
        "extractive_span": extractive_span,
        "source_record_id": record.record_id,
        "extraction_note": "First substantive sentence from text_ta of the source record",
    })
    derivation = (
        f"Question: '{question}'. "
        f"Gold is an extractive span from KB record {record.record_id} text_ta. "
        f"Span: '{extractive_span[:80]}...'"
    )

    item = BenchmarkItem(
        item_id=str(uuid.uuid4()),
        task_family="grounded_qa",
        template_name=template,
        template_version=TEMPLATE_VERSION,
        generator_script=GENERATOR_SCRIPT,
        primary_source_record_id=record.record_id,
        all_source_record_ids=json.dumps([record.record_id]),
        gold_answer=gold,
        gold_derivation=derivation,
        gold_status="derived",
        jurisdiction=record.jurisdiction,
        topic_tag=_derive_topic_tag(record),
        is_adversarial=False,
        created_at=datetime.now(timezone.utc),
    )
    _insert_item(item, result)


# ── Template 3: Closed-Book Legal QA ────────────────────────────────────────

def _create_closed_book_qa(record: KBRecord, result: GenerationResult) -> None:
    template = "closed_book_legal_qa_v1"
    if _item_exists(template, record.record_id):
        result.skipped.append(f"{template}:{record.record_id}")
        return

    question = (
        f"What does Section {record.section_no} of "
        f"{record.act_name_en} say? Cite the Act name and section number."
    )
    gold = json.dumps({
        "act_name_en": record.act_name_en,
        "act_name_ta": record.act_name_ta,
        "section_no": record.section_no,
        "text_ta": record.text_ta[:500] if record.text_ta else None,
        "text_en": record.text_en[:500] if record.text_en else None,
    })
    derivation = (
        f"Question asks about Section {record.section_no} of {record.act_name_en}. "
        f"Gold is the real content from KB record {record.record_id}. "
        f"Model must produce the correct Act name and section number."
    )

    item = BenchmarkItem(
        item_id=str(uuid.uuid4()),
        task_family="closed_book_legal_qa",
        template_name=template,
        template_version=TEMPLATE_VERSION,
        generator_script=GENERATOR_SCRIPT,
        primary_source_record_id=record.record_id,
        all_source_record_ids=json.dumps([record.record_id]),
        gold_answer=gold,
        gold_derivation=derivation,
        gold_status="derived",
        jurisdiction=record.jurisdiction,
        topic_tag=_derive_topic_tag(record),
        is_adversarial=False,
        created_at=datetime.now(timezone.utc),
    )
    _insert_item(item, result)


# ── Template 4: Jurisdiction Probe ──────────────────────────────────────────

def _create_jurisdiction_probes(
    by_jurisdiction: dict[str, list[KBRecord]],
    by_act: dict[str, list[KBRecord]],
    result: GenerationResult,
) -> None:
    """
    Pair real Central and real Tamil Nadu provisions on related subjects.
    Only where BOTH exist in the KB.
    """
    template = "jurisdiction_probe_v1"
    central = by_jurisdiction.get("Central", [])
    tn = by_jurisdiction.get("Tamil Nadu", [])

    if not central or not tn:
        result.errors.append(
            "Cannot create jurisdiction probes: need both Central and Tamil Nadu records"
        )
        return

    # Find topic overlaps: match by topic tag
    central_by_topic: dict[str, list[KBRecord]] = {}
    tn_by_topic: dict[str, list[KBRecord]] = {}
    for r in central:
        tag = _derive_topic_tag(r)
        central_by_topic.setdefault(tag, []).append(r)
    for r in tn:
        tag = _derive_topic_tag(r)
        tn_by_topic.setdefault(tag, []).append(r)

    common_topics = set(central_by_topic.keys()) & set(tn_by_topic.keys())

    for topic in common_topics:
        for c_rec in central_by_topic[topic]:
            for tn_rec in tn_by_topic[topic]:
                # Create two probe items — one showing Central text, one TN text
                for probe_rec, other_rec in [(c_rec, tn_rec), (tn_rec, c_rec)]:
                    if _item_exists(template, probe_rec.record_id):
                        result.skipped.append(f"{template}:{probe_rec.record_id}")
                        continue

                    gold = json.dumps({
                        "correct_jurisdiction": probe_rec.jurisdiction,
                        "act_name_en": probe_rec.act_name_en,
                        "section_no": probe_rec.section_no,
                        "paired_with": {
                            "jurisdiction": other_rec.jurisdiction,
                            "act_name_en": other_rec.act_name_en,
                            "record_id": other_rec.record_id,
                        },
                    })
                    derivation = (
                        f"Jurisdiction probe: shows text from {probe_rec.act_name_en} "
                        f"Section {probe_rec.section_no} ({probe_rec.jurisdiction}). "
                        f"Paired with {other_rec.act_name_en} ({other_rec.jurisdiction}) "
                        f"on topic '{topic}'. Model must identify correct jurisdiction."
                    )

                    item = BenchmarkItem(
                        item_id=str(uuid.uuid4()),
                        task_family="jurisdiction_probe",
                        template_name=template,
                        template_version=TEMPLATE_VERSION,
                        generator_script=GENERATOR_SCRIPT,
                        primary_source_record_id=probe_rec.record_id,
                        all_source_record_ids=json.dumps([probe_rec.record_id, other_rec.record_id]),
                        gold_answer=gold,
                        gold_derivation=derivation,
                        gold_status="derived",
                        jurisdiction=probe_rec.jurisdiction,
                        topic_tag=topic,
                        is_adversarial=False,
                        created_at=datetime.now(timezone.utc),
                    )
                    _insert_item(item, result)


# ── Template 5: Adversarial Perturbations ───────────────────────────────────

def _create_adversarial_items(
    records: list[KBRecord],
    by_act: dict[str, list[KBRecord]],
    rng: random.Random,
    result: GenerationResult,
) -> None:
    """
    Programmatic perturbations of real records:
    - wrong_act: put a real section number onto a different real Act
    - repealed_provision: present a repealed provision as current
    - flipped_jurisdiction: swap Central↔Tamil Nadu
    """
    act_names = list(by_act.keys())

    for record in records:
        # 5a. Wrong Act perturbation — assign this section to a different real Act
        template_wrong = "adversarial_wrong_act_v1"
        if not _item_exists(template_wrong, record.record_id):
            other_acts = [a for a in act_names if a != record.act_name_en]
            if other_acts:
                wrong_act = rng.choice(other_acts)
                perturbation = json.dumps({
                    "type": "wrong_act",
                    "original_act": record.act_name_en,
                    "substituted_act": wrong_act,
                    "section_no": record.section_no,
                    "description": (
                        f"Section {record.section_no} text is from "
                        f"'{record.act_name_en}', but the prompt claims it is from "
                        f"'{wrong_act}'. Model should detect the mismatch."
                    ),
                })
                gold = json.dumps({
                    "correct_act": record.act_name_en,
                    "claimed_act": wrong_act,
                    "section_no": record.section_no,
                    "expected_detection": "The model should identify that the text does not belong to the claimed Act.",
                })

                item = BenchmarkItem(
                    item_id=str(uuid.uuid4()),
                    task_family="adversarial",
                    template_name=template_wrong,
                    template_version=TEMPLATE_VERSION,
                    generator_script=GENERATOR_SCRIPT,
                    primary_source_record_id=record.record_id,
                    all_source_record_ids=json.dumps([record.record_id]),
                    gold_answer=gold,
                    gold_derivation=(
                        f"Adversarial: Section {record.section_no} from {record.act_name_en} "
                        f"attributed to {wrong_act}."
                    ),
                    gold_status="derived",
                    jurisdiction=record.jurisdiction,
                    topic_tag=_derive_topic_tag(record),
                    is_adversarial=True,
                    adversarial_perturbation=perturbation,
                    created_at=datetime.now(timezone.utc),
                )
                _insert_item(item, result)

        # 5b. Repealed provision — only for records where in_force is False
        if record.in_force is False:
            template_rep = "adversarial_repealed_v1"
            if not _item_exists(template_rep, record.record_id):
                perturbation = json.dumps({
                    "type": "repealed_as_current",
                    "act_name": record.act_name_en,
                    "repealed_by": record.repealed_by,
                    "description": (
                        f"Provision from repealed Act '{record.act_name_en}' "
                        f"presented as if currently in force."
                    ),
                })
                gold = json.dumps({
                    "in_force": False,
                    "repealed_by": record.repealed_by,
                    "expected_detection": "The model should identify that this provision is from a repealed Act.",
                })

                item = BenchmarkItem(
                    item_id=str(uuid.uuid4()),
                    task_family="adversarial",
                    template_name=template_rep,
                    template_version=TEMPLATE_VERSION,
                    generator_script=GENERATOR_SCRIPT,
                    primary_source_record_id=record.record_id,
                    all_source_record_ids=json.dumps([record.record_id]),
                    gold_answer=gold,
                    gold_derivation=(
                        f"Adversarial: Repealed provision from {record.act_name_en} "
                        f"presented as current law."
                    ),
                    gold_status="derived",
                    jurisdiction=record.jurisdiction,
                    topic_tag=_derive_topic_tag(record),
                    is_adversarial=True,
                    adversarial_perturbation=perturbation,
                    created_at=datetime.now(timezone.utc),
                )
                _insert_item(item, result)

        # 5c. Flipped jurisdiction — swap Central↔Tamil Nadu
        template_flip = "adversarial_flipped_jurisdiction_v1"
        if not _item_exists(template_flip, record.record_id):
            flipped = "Tamil Nadu" if record.jurisdiction == "Central" else "Central"
            perturbation = json.dumps({
                "type": "flipped_jurisdiction",
                "original_jurisdiction": record.jurisdiction,
                "claimed_jurisdiction": flipped,
                "description": (
                    f"Provision from {record.jurisdiction} Act "
                    f"presented as a {flipped} provision."
                ),
            })
            gold = json.dumps({
                "correct_jurisdiction": record.jurisdiction,
                "claimed_jurisdiction": flipped,
                "expected_detection": "The model should identify the correct jurisdiction.",
            })

            item = BenchmarkItem(
                item_id=str(uuid.uuid4()),
                task_family="adversarial",
                template_name=template_flip,
                template_version=TEMPLATE_VERSION,
                generator_script=GENERATOR_SCRIPT,
                primary_source_record_id=record.record_id,
                all_source_record_ids=json.dumps([record.record_id]),
                gold_answer=gold,
                gold_derivation=(
                    f"Adversarial: {record.jurisdiction} provision "
                    f"({record.act_name_en} s.{record.section_no}) "
                    f"presented as {flipped}."
                ),
                gold_status="derived",
                jurisdiction=record.jurisdiction,
                topic_tag=_derive_topic_tag(record),
                is_adversarial=True,
                adversarial_perturbation=perturbation,
                created_at=datetime.now(timezone.utc),
            )
            _insert_item(item, result)


# ── CLI entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent))
    res = generate_all_items()
    print(f"Generation complete: {res.total_generated} items")
    print(f"  By family: {res.by_family}")
    if res.skipped:
        print(f"  Skipped (already exist): {len(res.skipped)}")
    if res.errors:
        print(f"  Errors: {res.errors}")
