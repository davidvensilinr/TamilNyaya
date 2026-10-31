"""
db.py — SQLAlchemy database models and session management.

All tables include provenance fields where required by the spec.
Foreign key constraints and NOT NULL constraints enforce data integrity
at the DB layer, not just in Python.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from .config import settings

# ── Engine ─────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite only
    echo=False,
)


# Enable WAL mode and foreign keys for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Base ───────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Audit log ──────────────────────────────────────────────────────────────────
class AuditEntry(Base):
    __tablename__ = "audit_log"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    timestamp: datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    level: str = Column(String(16), nullable=False)          # INFO|WARNING|ERROR|RETRY
    action: str = Column(String(64), nullable=False, index=True)
    detail: str = Column(Text, nullable=False)
    run_id: Optional[str] = Column(String(36), index=True)
    item_id: Optional[str] = Column(String(64), index=True)
    source_url: Optional[str] = Column(Text)
    traceback: Optional[str] = Column(Text)


# ── Knowledge Base ─────────────────────────────────────────────────────────────
class KBRecord(Base):
    """
    One section (or article) ingested from a real official source.

    Provenance fields are NOT NULL where the spec says mandatory.
    text_en is nullable because we only store it if the source provides it.
    """
    __tablename__ = "kb_records"

    record_id: str = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    act_name_ta: str = Column(Text, nullable=False)
    act_name_en: str = Column(Text, nullable=False)
    section_no: str = Column(String(32), nullable=False)
    text_ta: str = Column(Text, nullable=False)
    text_en: Optional[str] = Column(Text)                    # only if source provides it
    jurisdiction: str = Column(
        String(16), nullable=False,
        # Enforced at DB level
    )
    in_force: Optional[bool] = Column(Boolean)               # null = unknown
    repealed_by: Optional[str] = Column(Text)
    as_of_date: Optional[str] = Column(String(32))           # ISO date string from source
    source_url: str = Column(Text, nullable=False)
    source_document_title: str = Column(Text, nullable=False)
    source_file_sha256: str = Column(String(64), nullable=False, index=True)
    retrieved_at: datetime = Column(DateTime(timezone=True), nullable=False)
    parser_name_and_version: str = Column(String(128), nullable=False)
    extraction_method: str = Column(String(16), nullable=False)  # html_parse|pdf_text|ocr
    ocr_confidence: Optional[float] = Column(Float)          # null unless OCR
    raw_span: Optional[str] = Column(Text)                   # page no. or char offsets

    __table_args__ = (
        CheckConstraint(
            "jurisdiction IN ('Central', 'Tamil Nadu')",
            name="ck_jurisdiction",
        ),
        CheckConstraint(
            "extraction_method IN ('html_parse', 'pdf_text', 'ocr')",
            name="ck_extraction_method",
        ),
        UniqueConstraint("source_file_sha256", "section_no", name="uq_file_section"),
    )

    # Relationships
    benchmark_items = relationship("BenchmarkItem", back_populates="source_record", foreign_keys="BenchmarkItem.primary_source_record_id")


# ── Coverage tracking ──────────────────────────────────────────────────────────
class ActCoverage(Base):
    """
    Tracks how many sections exist in the source vs how many we ingested.
    Populated by the coverage module after each ingestion run.
    """
    __tablename__ = "act_coverage"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    act_name_en: str = Column(Text, nullable=False, unique=True)
    jurisdiction: str = Column(String(16), nullable=False)
    sections_in_source: Optional[int] = Column(Integer)      # null if not declared by source
    sections_ingested: int = Column(Integer, nullable=False, default=0)
    coverage_note: Optional[str] = Column(Text)
    last_updated: datetime = Column(DateTime(timezone=True), nullable=False)


# ── Benchmark items ────────────────────────────────────────────────────────────
class BenchmarkItem(Base):
    __tablename__ = "benchmark_items"

    item_id: str = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_family: str = Column(String(32), nullable=False)    # citation_completion | grounded_qa | …
    template_name: str = Column(String(64), nullable=False)
    template_version: str = Column(String(16), nullable=False)
    generator_script: str = Column(Text, nullable=False)
    primary_source_record_id: str = Column(
        String(64), ForeignKey("kb_records.record_id"), nullable=False
    )
    all_source_record_ids: str = Column(Text, nullable=False)  # JSON array of record_ids
    gold_answer: Optional[str] = Column(Text)
    gold_derivation: Optional[str] = Column(Text)             # how gold was derived
    gold_status: str = Column(
        String(32), nullable=False, default="derived"
    )  # derived | needs_human_annotation | human_labeled
    jurisdiction: str = Column(String(16), nullable=False)
    topic_tag: str = Column(String(64), nullable=False)
    is_adversarial: bool = Column(Boolean, nullable=False, default=False)
    adversarial_perturbation: Optional[str] = Column(Text)    # JSON describing the change
    created_at: datetime = Column(DateTime(timezone=True), nullable=False)

    source_record = relationship("KBRecord", back_populates="benchmark_items", foreign_keys=[primary_source_record_id])
    run_results = relationship("RunResult", back_populates="item")
    annotations = relationship("Annotation", back_populates="item")


# ── Evaluation runs ────────────────────────────────────────────────────────────
class EvalRun(Base):
    __tablename__ = "eval_runs"

    run_id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at: datetime = Column(DateTime(timezone=True), nullable=False)
    completed_at: Optional[datetime] = Column(DateTime(timezone=True))
    status: str = Column(String(16), nullable=False, default="pending")  # pending|running|done|failed|interrupted
    model_id: str = Column(Text, nullable=False)
    provider: str = Column(String(32), nullable=False, default="groq")
    temperature: float = Column(Float, nullable=False, default=0.0)
    max_tokens: int = Column(Integer, nullable=False, default=512)
    seed: Optional[int] = Column(Integer)
    system_prompt: Optional[str] = Column(Text)
    config_snapshot: str = Column(Text, nullable=False)       # JSON of settings.safe_dict()
    dataset_hash: Optional[str] = Column(String(64))          # SHA-256 of items used
    kb_hash: Optional[str] = Column(String(64))               # SHA-256 of KB state
    total_items: int = Column(Integer, nullable=False, default=0)
    completed_items: int = Column(Integer, nullable=False, default=0)
    error_count: int = Column(Integer, nullable=False, default=0)
    resume_from_item: Optional[str] = Column(String(64))      # for resumability

    results = relationship("RunResult", back_populates="run")


# ── Per-item run results ───────────────────────────────────────────────────────
class RunResult(Base):
    __tablename__ = "run_results"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    run_id: str = Column(String(36), ForeignKey("eval_runs.run_id"), nullable=False, index=True)
    item_id: str = Column(String(64), ForeignKey("benchmark_items.item_id"), nullable=False, index=True)
    timestamp: datetime = Column(DateTime(timezone=True), nullable=False)

    # Raw LLM output — NEVER EDITED
    system_prompt: Optional[str] = Column(Text)
    user_prompt: str = Column(Text, nullable=False)
    raw_response: str = Column(Text, nullable=False)
    latency_ms: int = Column(Integer)
    prompt_tokens: Optional[int] = Column(Integer)
    completion_tokens: Optional[int] = Column(Integer)
    http_status: Optional[int] = Column(Integer)
    retry_count: int = Column(Integer, nullable=False, default=0)
    error_message: Optional[str] = Column(Text)

    # Verification results (JSON blobs)
    layer1_result: Optional[str] = Column(Text)               # JSON CitationVerificationResult
    layer2_result: Optional[str] = Column(Text)               # JSON FaithfulnessResult
    layer3_result: Optional[str] = Column(Text)               # JSON JudgeResult

    # Aggregated error labels
    error_categories: Optional[str] = Column(Text)            # JSON array
    max_severity: Optional[int] = Column(Integer)

    run = relationship("EvalRun", back_populates="results")
    item = relationship("BenchmarkItem", back_populates="run_results")


# ── Annotations ───────────────────────────────────────────────────────────────
class Annotation(Base):
    __tablename__ = "annotations"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    item_id: str = Column(String(64), ForeignKey("benchmark_items.item_id"), nullable=False, index=True)
    run_result_id: Optional[int] = Column(Integer, ForeignKey("run_results.id"))
    annotator_id: str = Column(String(64), nullable=False)
    timestamp: datetime = Column(DateTime(timezone=True), nullable=False)
    error_categories: str = Column(Text, nullable=False)      # JSON array
    severity: int = Column(Integer, nullable=False)
    notes: Optional[str] = Column(Text)
    is_adjudicated: bool = Column(Boolean, nullable=False, default=False)
    adjudicated_by: Optional[str] = Column(String(64))

    item = relationship("BenchmarkItem", back_populates="annotations")

    __table_args__ = (
        UniqueConstraint("item_id", "annotator_id", name="uq_annotation_per_annotator"),
    )


def create_all_tables() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
