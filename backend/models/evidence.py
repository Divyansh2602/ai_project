import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .database import Base


def _uuid():
    return str(uuid.uuid4())


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(SAEnum("image", "video", "audio", "document", name="file_type_enum"), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_hash = Column(String(64), nullable=False)
    status = Column(
        SAEnum("pending", "analyzing", "done", "failed", name="status_enum"),
        default="pending",
        nullable=False,
    )
    upload_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    agent_results = relationship("AgentResult", back_populates="evidence", cascade="all, delete-orphan")
    verdict = relationship("FinalVerdict", back_populates="evidence", uselist=False, cascade="all, delete-orphan")
    audit_log = relationship("AuditLog", back_populates="evidence", uselist=False, cascade="all, delete-orphan")


class AgentResult(Base):
    __tablename__ = "agent_results"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    evidence_id = Column(UUID(as_uuid=False), ForeignKey("evidence.id"), nullable=False)
    agent_name = Column(String(64), nullable=False)
    findings = Column(JSONB, default=dict)
    confidence_score = Column(Float, nullable=True)
    heatmap_path = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    evidence = relationship("Evidence", back_populates="agent_results")


class FinalVerdict(Base):
    __tablename__ = "final_verdicts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    evidence_id = Column(UUID(as_uuid=False), ForeignKey("evidence.id"), nullable=False, unique=True)
    verdict = Column(
        SAEnum("Authentic", "Fake", "Inconclusive", name="verdict_enum"),
        nullable=False,
    )
    overall_score = Column(Float, nullable=False)
    manipulation_type = Column(String(128), nullable=True)
    manipulation_confidence = Column(Float, nullable=True)
    gan_attribution = Column(String(128), nullable=True)
    gan_confidence = Column(Float, nullable=True)
    reasoning = Column(JSONB, default=list)
    llm_summary = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    evidence = relationship("Evidence", back_populates="verdict")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    evidence_id = Column(UUID(as_uuid=False), ForeignKey("evidence.id"), nullable=False, unique=True)
    blockchain_hash = Column(String(256), nullable=True)          # anchor tx hash
    blockchain_network = Column(String(32), nullable=True)        # e.g. polygon-amoy
    blockchain_status = Column(String(32), nullable=True)         # anchored|pending|skipped|error
    record_signature = Column(Text, nullable=True)                # Ed25519 sig (hex) over signed_payload
    signature_algorithm = Column(String(32), nullable=True)
    signature_key_fingerprint = Column(String(128), nullable=True)
    signed_payload = Column(JSONB, nullable=True)                 # exact record the signature covers
    chain_of_custody = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    evidence = relationship("Evidence", back_populates="audit_log")
