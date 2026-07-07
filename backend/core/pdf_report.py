"""Legal Evidence Package PDF (Phase 6).

Builds a court-admissible-style forensic report with reportlab:

  - Case header: file identity, SHA-256, upload time, verdict
  - Manipulation type + generator attribution
  - Per-agent findings tables
  - XAI exhibits: ELA heatmap, Grad-CAM heatmap, metadata feature-importance
    chart, video confidence timeline (tampered segments in red)
  - Chain of custody log + blockchain anchor proof
  - Ed25519 record signature block (algorithm, key fingerprint, signature)

`build_pdf(...)` takes the already-loaded ORM rows and returns the output path.
Charts are rendered on demand (matplotlib/Agg via core.xai) so the Celery
worker never pays for them — only the report download does.
"""
import os
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

from core import xai

REPORT_DIR = os.getenv("REPORT_DIR", "reports")

_VERDICT_COLORS = {
    "Authentic": "#2da44e",
    "Fake": "#d73a49",
    "Inconclusive": "#bf8700",
}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Small", parent=ss["Normal"], fontSize=8, leading=10))
    ss.add(ParagraphStyle("Mono", parent=ss["Normal"], fontName="Courier",
                          fontSize=7, leading=9))
    ss.add(ParagraphStyle("SectionH", parent=ss["Heading2"], spaceBefore=14))
    return ss


def _kv_table(rows, col0=4.5 * cm, col1=11.5 * cm):
    t = Table(rows, colWidths=[col0, col1])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#dddddd")),
    ]))
    return t


def _image_if_exists(path, max_w=8 * cm, max_h=6.5 * cm):
    if not path or not os.path.exists(path):
        return None
    try:
        from PIL import Image as PILImage
        w, h = PILImage.open(path).size
        scale = min(max_w / w, max_h / h, 1.0)
        return Image(path, width=w * scale, height=h * scale)
    except Exception:
        return None


def build_pdf(evidence, verdict, agent_results, audit) -> str:
    """Render the evidence package. Returns the PDF path."""
    ss = _styles()
    os.makedirs(REPORT_DIR, exist_ok=True)
    out_path = os.path.join(REPORT_DIR, f"evidence_{evidence.id}.pdf")

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title=f"TrustSphere Evidence Report {evidence.id}",
    )
    story = []

    # ── Header ──
    story.append(Paragraph("TrustSphere AI — Digital Evidence Verification Report", ss["Title"]))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} · "
        f"Case ID {evidence.id}", ss["Small"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#333333"),
                            spaceBefore=6, spaceAfter=10))

    # ── 1. Evidence identity ──
    story.append(Paragraph("1. Evidence Identification", ss["SectionH"]))
    story.append(_kv_table([
        ["Original filename", evidence.original_filename],
        ["File type", evidence.file_type],
        ["SHA-256 hash", Paragraph(evidence.file_hash, ss["Mono"])],
        ["Uploaded (UTC)", evidence.upload_time.isoformat() if evidence.upload_time else "—"],
        ["Analysis status", evidence.status],
    ]))

    # ── 2. Verdict ──
    story.append(Paragraph("2. Forensic Verdict", ss["SectionH"]))
    v_label = verdict.verdict if verdict else "Unknown"
    v_color = _VERDICT_COLORS.get(v_label, "#000000")
    story.append(Paragraph(
        f'<font color="{v_color}"><b>{v_label.upper()}</b></font> — overall authenticity score '
        f'{verdict.overall_score:.2f} (0 = fake, 1 = authentic)' if verdict else "No verdict recorded.",
        ss["Normal"]))
    if verdict:
        rows = []
        if verdict.manipulation_type:
            rows.append(["Manipulation type",
                         f"{verdict.manipulation_type} (confidence {verdict.manipulation_confidence:.2f})"])
        if verdict.gan_attribution:
            rows.append(["Generator attribution",
                         f"{verdict.gan_attribution} (confidence {verdict.gan_confidence:.2f})"])
        if rows:
            story.append(Spacer(1, 4))
            story.append(_kv_table(rows))
        if verdict.reasoning:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Reasoning:", ss["Small"]))
            for r in verdict.reasoning:
                story.append(Paragraph(f"• {escape(str(r))}", ss["Small"]))
        if verdict.llm_summary:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Forensic summary:", ss["Small"]))
            story.append(Paragraph(escape(verdict.llm_summary), ss["Normal"]))

    # ── 3. Agent findings ──
    story.append(Paragraph("3. Agent Findings", ss["SectionH"]))
    for ar in agent_results:
        conf = f"{ar.confidence_score:.3f}" if ar.confidence_score is not None else "n/a (no signal)"
        story.append(Paragraph(f"<b>{ar.agent_name}</b> — authenticity {conf}", ss["Normal"]))
        data = [["Check", "Status", "Note"]]
        for f in (ar.findings or []):
            # Findings notes may contain raw exception text with <, >, & —
            # Paragraph parses XML, so escape or the whole PDF build crashes.
            data.append([f.get("check", ""), f.get("status", ""),
                         Paragraph(escape(str(f.get("note", ""))), ss["Small"])])
        t = Table(data, colWidths=[3.2 * cm, 2.2 * cm, 10.6 * cm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    # ── 4. XAI exhibits ──
    exhibits = []
    for ar in agent_results:
        extras = ar.extras or {}
        ela = _image_if_exists(ar.heatmap_path)
        if ela:
            exhibits.append((f"Exhibit — {ar.agent_name}: ELA heatmap "
                             "(bright regions compress inconsistently → possible splice)", ela))
        cam = _image_if_exists(extras.get("gradcam_path"))
        if cam:
            method = extras.get("gradcam_method", "gradcam")
            exhibits.append((f"Exhibit — {ar.agent_name}: model attention map ({method}) "
                             "— regions that drove the deepfake classifier's decision", cam))
        fi = extras.get("feature_importance")
        if fi:
            chart_path = os.path.join(REPORT_DIR, f"tmp_{evidence.id}_shap.png")
            if xai.render_importance_chart(fi, chart_path):
                img = _image_if_exists(chart_path, max_w=12 * cm, max_h=8 * cm)
                if img:
                    exhibits.append(("Exhibit — metadata feature importance "
                                     "(exact Shapley contributions; green → authentic, red → fake)", img))
        fs = extras.get("frame_scores")
        if fs:
            chart_path = os.path.join(REPORT_DIR, f"tmp_{evidence.id}_timeline.png")
            segs = extras.get("flagged_segments") or []
            if xai.render_timeline_chart(fs, segs, chart_path):
                img = _image_if_exists(chart_path, max_w=14 * cm, max_h=6 * cm)
                if img:
                    exhibits.append(("Exhibit — video confidence timeline "
                                     "(per-frame authenticity; flagged segments shaded red)", img))

    if exhibits:
        story.append(Paragraph("4. Explainability Exhibits (XAI)", ss["SectionH"]))
        for caption, img in exhibits:
            story.append(Paragraph(caption, ss["Small"]))
            story.append(img)
            story.append(Spacer(1, 10))

    # ── 5. Chain of custody + blockchain ──
    story.append(Paragraph("5. Chain of Custody", ss["SectionH"]))
    custody = (audit.chain_of_custody if audit else None) or []
    if custody:
        data = [["Event", "Timestamp (UTC)", "Detail"]]
        for ev in custody:
            detail = ev.get("detail") or ev.get("key_fingerprint") or ev.get("tx_hash") or ""
            data.append([ev.get("event", ""), ev.get("timestamp", ""),
                         Paragraph(escape(str(detail)), ss["Mono"])])
        t = Table(data, colWidths=[3.6 * cm, 5.4 * cm, 7 * cm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No custody log recorded.", ss["Small"]))

    if audit:
        story.append(Spacer(1, 6))
        rows = [["Blockchain network", audit.blockchain_network or "—"],
                ["Anchor status", audit.blockchain_status or "—"]]
        if audit.blockchain_hash:
            rows.append(["Anchor transaction", Paragraph(
                f"https://amoy.polygonscan.com/tx/{audit.blockchain_hash}", ss["Mono"])])
        story.append(_kv_table(rows))

    # ── 6. Digital signature ──
    story.append(Paragraph("6. Record Integrity — Digital Signature", ss["SectionH"]))
    if audit and audit.record_signature:
        story.append(Paragraph(
            "The analysis record below is signed with the TrustSphere server's "
            "Ed25519 key. Any alteration of the signed payload invalidates the "
            "signature (verifiable via GET /api/verify/{file_id}).", ss["Small"]))
        story.append(Spacer(1, 4))
        story.append(_kv_table([
            ["Algorithm", audit.signature_algorithm or "Ed25519"],
            ["Key fingerprint", Paragraph(audit.signature_key_fingerprint or "—", ss["Mono"])],
            ["Signature", Paragraph(audit.record_signature, ss["Mono"])],
        ]))
    else:
        story.append(Paragraph("No signature recorded for this analysis.", ss["Small"]))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#999999")))
    story.append(Paragraph(
        "This report was generated automatically by TrustSphere AI. The verdict is a "
        "statistical forensic assessment, not a legal determination.", ss["Small"]))

    doc.build(story)

    # Charts embedded above are baked into the PDF — clean up temp PNGs.
    for suffix in ("shap", "timeline"):
        tmp = os.path.join(REPORT_DIR, f"tmp_{evidence.id}_{suffix}.png")
        try:
            os.remove(tmp)
        except OSError:
            pass

    return out_path
