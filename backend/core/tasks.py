import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from .celery_app import celery_app
from .decision_engine import decide
from .llm_summary import generate_summary
from models.database import SessionLocal
from models.evidence import Evidence, AgentResult, FinalVerdict, AuditLog

from agents import metadata_agent, image_agent, video_agent, audio_agent, security_agent
from security import signing, blockchain


def _extract_audio_track(video_path: str) -> str | None:
    """Pull the audio track out of a video with ffmpeg, if present."""
    try:
        out_path = os.path.join(tempfile.gettempdir(),
                                f"ts_audio_{os.path.basename(video_path)}.wav")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", out_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )
        if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        logger.warning("audio track extraction failed for %s (ffmpeg exit %s)",
                       video_path, result.returncode)
    except FileNotFoundError:
        logger.warning("ffmpeg not installed — skipping audio analysis for video %s", video_path)
    except Exception:
        logger.warning("audio track extraction failed for %s", video_path, exc_info=True)
    return None


def _run_agents(file_type: str, file_path: str) -> list[dict]:
    results = []
    if file_type == "image":
        results.append(metadata_agent.run(file_path))
        results.append(image_agent.run(file_path))
    elif file_type == "video":
        results.append(metadata_agent.run(file_path))
        results.append(video_agent.run(file_path))
        audio_path = _extract_audio_track(file_path)
        if audio_path:
            results.append(audio_agent.run(audio_path))
            try:
                os.remove(audio_path)
            except OSError:
                pass
    elif file_type == "audio":
        results.append(metadata_agent.run(file_path))
        results.append(audio_agent.run(file_path))
    else:  # document
        results.append(metadata_agent.run(file_path))
    # Provenance checks (C2PA + watermark) run on every file type.
    results.append(security_agent.run(file_path))
    return results


@celery_app.task(bind=True, name="core.tasks.analyze_evidence")
def analyze_evidence(self, evidence_id: str):
    db = SessionLocal()
    try:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            return {"error": "evidence not found"}

        evidence.status = "analyzing"
        # Re-analysis: clear previous results first — final_verdicts/audit_logs
        # are unique per evidence_id, so a second run would IntegrityError.
        db.query(AgentResult).filter(AgentResult.evidence_id == evidence_id).delete()
        db.query(FinalVerdict).filter(FinalVerdict.evidence_id == evidence_id).delete()
        db.query(AuditLog).filter(AuditLog.evidence_id == evidence_id).delete()
        db.commit()

        agent_results = _run_agents(evidence.file_type, evidence.file_path)

        for result in agent_results:
            # Phase 6: persist agent-specific extras (frame_scores, gradcam_path,
            # feature_importance, ...) — everything beyond the core fields.
            core_keys = {"agent", "confidence", "findings", "heatmap_path"}
            extras = {k: v for k, v in result.items() if k not in core_keys}
            ar = AgentResult(
                evidence_id=evidence_id,
                agent_name=result["agent"],
                findings=result.get("findings", []),
                confidence_score=result.get("confidence"),
                heatmap_path=result.get("heatmap_path"),
                extras=extras or None,
            )
            db.add(ar)

        db.flush()

        decision = decide(agent_results, evidence.file_type)

        # Phase 6: optional local-LLM narrative summary (env-gated, fail-safe).
        llm_summary = generate_summary(
            decision, agent_results,
            {
                "original_filename": evidence.original_filename,
                "file_type": evidence.file_type,
                "file_hash": evidence.file_hash,
            },
        )

        fv = FinalVerdict(
            evidence_id=evidence_id,
            verdict=decision["verdict"],
            overall_score=decision["overall_score"],
            manipulation_type=decision["manipulation_type"],
            manipulation_confidence=decision["manipulation_confidence"],
            gan_attribution=decision["gan_attribution"],
            gan_confidence=decision["gan_confidence"],
            reasoning=decision["reasoning"],
            llm_summary=llm_summary,
        )
        db.add(fv)

        custody = [
            {"event": "uploaded", "timestamp": evidence.upload_time.isoformat()},
            {"event": "analyzed", "timestamp": datetime.now(timezone.utc).isoformat()},
        ]

        # ── Phase 5.2: sign the evidence record ──
        signed_payload = {
            "evidence_id": evidence_id,
            "file_hash": evidence.file_hash,
            "original_filename": evidence.original_filename,
            "file_type": evidence.file_type,
            "verdict": decision["verdict"],
            "overall_score": decision["overall_score"],
            "manipulation_type": decision["manipulation_type"],
            "gan_attribution": decision["gan_attribution"],
            "agent_confidences": {r["agent"]: r.get("confidence") for r in agent_results},
            "analyzed_at": custody[-1]["timestamp"],
        }
        sig = signing.sign_record(signed_payload)
        custody.append({"event": "signed", "timestamp": sig["signed_at"],
                        "key_fingerprint": sig["key_fingerprint"]})

        # ── Phase 5.3: anchor on Polygon (never fails the pipeline) ──
        anchor = blockchain.anchor_verdict(evidence.file_hash, decision["verdict"])
        custody.append({
            "event": f"blockchain_{anchor['status']}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "network": anchor["network"],
            "tx_hash": anchor["tx_hash"],
            "detail": anchor["reason"] or anchor["explorer_url"],
        })

        al = AuditLog(
            evidence_id=evidence_id,
            blockchain_hash=anchor["tx_hash"],
            blockchain_network=anchor["network"],
            blockchain_status=anchor["status"],
            record_signature=sig["signature"],
            signature_algorithm=sig["algorithm"],
            signature_key_fingerprint=sig["key_fingerprint"],
            signed_payload=signed_payload,
            chain_of_custody=custody,
        )
        db.add(al)

        evidence.status = "done"
        db.commit()

        return {
            "evidence_id": evidence_id,
            "verdict": decision["verdict"],
            "overall_score": decision["overall_score"],
            "manipulation_type": decision["manipulation_type"],
            "gan_attribution": decision["gan_attribution"],
        }

    except Exception as exc:
        db.rollback()
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if evidence:
            evidence.status = "failed"
            db.commit()
        raise exc
    finally:
        db.close()
