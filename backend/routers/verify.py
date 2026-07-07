"""Evidence integrity verification endpoint (Phase 5).

GET /api/verify/{file_id} re-checks, live:
  1. file integrity  — SHA-256 of the file on disk vs the hash stored at upload
  2. record signature — Ed25519 signature over the stored signed_payload
  3. blockchain anchor — reads the verdict back from the Polygon Amoy contract

Together these prove the evidence file, the analysis record, and the on-chain
anchor still agree.
"""
import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.database import get_db
from models.evidence import Evidence, AuditLog
from security import signing, blockchain

router = APIRouter(prefix="/api", tags=["verify"])


@router.get("/verify/{file_id}")
def verify_evidence(file_id: str, db: Session = Depends(get_db)):
    evidence = db.query(Evidence).filter(Evidence.id == file_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    audit = db.query(AuditLog).filter(AuditLog.evidence_id == file_id).first()

    # 1. File integrity
    file_check = {"status": "missing", "stored_hash": evidence.file_hash, "current_hash": None}
    if os.path.exists(evidence.file_path):
        with open(evidence.file_path, "rb") as f:
            current = hashlib.sha256(f.read()).hexdigest()
        file_check["current_hash"] = current
        file_check["status"] = "intact" if current == evidence.file_hash else "TAMPERED"

    # 2. Record signature
    sig_check = {"status": "not_signed"}
    if audit and audit.record_signature and audit.signed_payload:
        valid = signing.verify_record(audit.signed_payload, audit.record_signature)
        sig_check = {
            "status": "valid" if valid else "INVALID",
            "algorithm": audit.signature_algorithm,
            "key_fingerprint": audit.signature_key_fingerprint,
        }

    # 3. Blockchain anchor
    chain_check = {"status": audit.blockchain_status if audit else "not_anchored",
                   "tx_hash": audit.blockchain_hash if audit else None,
                   "network": audit.blockchain_network if audit else None,
                   "on_chain_record": None}
    if audit and audit.blockchain_status in ("anchored", "pending"):
        on_chain = blockchain.read_verdict(evidence.file_hash)
        if on_chain:
            chain_check["on_chain_record"] = on_chain
            local_verdict = (audit.signed_payload or {}).get("verdict")
            chain_check["status"] = (
                "verified" if on_chain["verdict"] == local_verdict else "MISMATCH"
            )

    overall_ok = (
        file_check["status"] == "intact"
        and sig_check["status"] == "valid"
        and chain_check["status"] not in ("MISMATCH",)
    )

    return {
        "file_id": file_id,
        "verified": overall_ok,
        "file_integrity": file_check,
        "record_signature": sig_check,
        "blockchain_anchor": chain_check,
        "chain_of_custody": audit.chain_of_custody if audit else [],
    }
