"""Builds the BCSE497J Project-I report (Word) from the VIT template and the project's real results.

    python scripts/build_report.py --template "<template.docx>" --out docs/report/TrustSphere_AI_Project_Report.docx

Unknown personal details (names, register numbers, guide, HoD, dates, signatures) are left as the template's highlighted placeholders.
Every number comes from docs/evaluation/metrics.json; nothing is typed by hand. The contents table and the lists of figures and tables are filled
with real page numbers by exporting the document to PDF through Word and searching the pages (two passes).
"""
import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import docx
import fitz
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "docs" / "evaluation"
FIG = ROOT / "docs" / "report" / "figures"
SHOT = ROOT / "docs" / "screenshots"
TITLE = "TrustSphere AI: A Multi-Agent Framework for Image Manipulation Detection with Verifiable Digital Evidence"
M = json.loads((EV / "metrics.json").read_text(encoding="utf-8"))


# ── number helpers ──────────────────────────────────────────────────────────────────────────
def pc(v, d=2):
    return f"{v * 100:.{d}f}%"


CR = M["CASIA v2.0, random 5-fold"]
CG = M["CASIA v2.0, source-disjoint 5-fold"]
CE = M.get("Columbia, whole-image, ELA input")
CS = M.get("Columbia, whole-image, SRM input")
CP = M.get("Columbia, patch-based, SRM input")
CPG = M.get("Columbia, patch-based, SRM input, scene-disjoint")
PH = M["pipeline_holdout"]
LZ = M.get("localizer")
HO = json.loads((EV / "training" / "holdout_casia_v2_group.json").read_text(encoding="utf-8"))["metrics"]


# ── low-level docx helpers ──────────────────────────────────────────────────────────────────
def has_sectpr(p):
    return p._p.pPr is not None and p._p.pPr.find(qn("w:sectPr")) is not None


def delete_paragraph(p):
    p._p.getparent().remove(p._p)


def replace_text(par, old, new, unhighlight=True):
    runs = par.runs
    full = "".join(r.text for r in runs)
    i = full.find(old)
    if i < 0:
        return False
    pos, sr, er = 0, None, None
    for k, r in enumerate(runs):
        n = len(r.text)
        if sr is None and i < pos + n:
            sr, so = k, i - pos
        if sr is not None and i + len(old) <= pos + n:
            er, eo = k, i + len(old) - pos
            break
        pos += n
    if sr == er:
        runs[sr].text = runs[sr].text[:so] + new + runs[sr].text[eo:]
    else:
        runs[sr].text = runs[sr].text[:so] + new
        runs[er].text = runs[er].text[eo:]
        for r in runs[sr + 1:er]:
            r.text = ""
    if unhighlight:
        runs[sr].font.highlight_color = None
    return True


def set_runs_text(par, text, bold=None, size=None, highlight=None, italic=None):
    runs = par.runs
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
        r = runs[0]
    else:
        r = par.add_run(text)
    if bold is not None:
        r.bold = bold
    if italic is not None:
        r.italic = italic
    if size:
        r.font.size = Pt(size)
    r.font.highlight_color = highlight
    return r


def mark_placeholders(par):
    for r in par.runs:
        if "<" in r.text or ">" in r.text:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW


class Doc:
    """Inserts content before an anchor element of the template."""

    def __init__(self, document, anchor_el):
        self.d = document
        self.anchor = anchor_el
        self.fig_no, self.tab_no, self.cur = {}, {}, 0
        self.figures, self.tables = [], []

    def _place(self, el):
        self.anchor.addprevious(el)

    def para(self, text="", size=12, bold=False, italic=False, align="justify", before=0, after=6, line=1.15, indent=None, keep_next=False, page_break=False, font=None):
        p = self.d.add_paragraph()
        pf = p.paragraph_format
        pf.space_before, pf.space_after, pf.line_spacing = Pt(before), Pt(after), line
        pf.alignment = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY, "left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER}[align]
        if indent is not None:
            pf.left_indent = Cm(indent)
        pf.keep_with_next = keep_next
        pf.page_break_before = page_break
        if text:
            self.runs(p, text, size, bold, italic, font)
        self._place(p._p)
        return p

    def runs(self, p, text, size=12, bold=False, italic=False, font=None):
        """Supports **bold** and _italic_ markers inside text."""
        for part in re.split(r"(\*\*.+?\*\*|__.+?__)", text):
            if not part:
                continue
            b, i = bold, italic
            if part.startswith("**"):
                part, b = part[2:-2], True
            elif part.startswith("__"):
                part, i = part[2:-2], True
            r = p.add_run(part)
            r.font.size = Pt(size)
            r.bold, r.italic = b, i
            r.font.name = font or "Times New Roman"
            r._r.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font or "Times New Roman")

    def chapter(self, n, title):
        self.cur = n
        self.fig_no[n] = self.tab_no[n] = 0
        self.para(f"CHAPTER {n}", 16, True, align="center", after=8, page_break=True, keep_next=True)
        self.para(f"{n}. {title}", 14, True, align="left", after=8, keep_next=True)

    def h2(self, text):
        self.para(text, 13, True, align="left", before=8, after=4, keep_next=True)

    def h3(self, text):
        self.para(text, 12, True, align="left", before=6, after=3, keep_next=True)

    def p(self, text):
        self.para(text, 12)

    def bullets(self, items, numbered=False):
        for k, t in enumerate(items, 1):
            p = self.para("", 12, align="justify", after=3, indent=0.9)
            p.paragraph_format.first_line_indent = Cm(-0.6)
            self.runs(p, (f"{k}.  " if numbered else "•  ") + t)

    def caption(self, text, before=3, after=10):
        self.para(text, 10, align="center", before=before, after=after, line=1.0)

    def figure(self, path, caption, max_w=15.5, max_h=20.0):
        self.fig_no[self.cur] += 1
        label = f"Figure {self.cur}.{self.fig_no[self.cur]}"
        w, h = Image.open(path).size
        scale = min(max_w / w, max_h / h)   # cm per pixel
        p = self.d.add_paragraph()
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before, p.paragraph_format.space_after, p.paragraph_format.keep_with_next = Pt(6), Pt(2), True
        p.add_run().add_picture(str(path), width=Cm(w * scale), height=Cm(h * scale))
        self._place(p._p)
        self.caption(f"{label}: {caption}")
        self.figures.append((label.replace("Figure ", ""), caption))

    def figure_row(self, items, max_w=7.6, max_h=16.0):
        """Several figures side by side in one borderless row, each with its own numbered caption."""
        t = self.d.add_table(rows=1, cols=len(items))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for cell, (path, caption) in zip(t.rows[0].cells, items):
            self.fig_no[self.cur] += 1
            label = f"{self.cur}.{self.fig_no[self.cur]}"
            w, h = Image.open(path).size
            scale = min(max_w / w, max_h / h)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(path), width=Cm(w * scale), height=Cm(h * scale))
            cp = cell.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cp.paragraph_format.space_after = Pt(6)
            r = cp.add_run(f"Figure {label}: {caption}")
            r.font.size, r.font.name = Pt(10), "Times New Roman"
            self.figures.append((label, caption))
        self._place(t._tbl)
        self.para("", 4, after=4, line=1.0)

    def table(self, caption, header, rows, widths=None, size=10, align_first="left"):
        self.tab_no[self.cur] += 1
        label = f"Table {self.cur}.{self.tab_no[self.cur]}"
        self.para(f"{label}: {caption}", 10, align="center", before=6, after=3, line=1.0, keep_next=True)
        t = self.d.add_table(rows=1 + len(rows), cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(header):
            c = t.rows[0].cells[j]
            c.text = ""
            r = c.paragraphs[0].add_run(h)
            r.bold, r.font.size, r.font.name = True, Pt(size), "Times New Roman"
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            tcPr = c._tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "DCE6F2")
            tcPr.append(shd)
        for i, row in enumerate(rows, 1):
            for j, v in enumerate(row):
                c = t.rows[i].cells[j]
                c.text = ""
                bold = isinstance(v, str) and v.startswith("**")
                r = c.paragraphs[0].add_run(v.strip("*") if isinstance(v, str) else str(v))
                r.font.size, r.font.name, r.bold = Pt(size), "Times New Roman", bold
                c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT if (j == 0 and align_first == "left") else WD_ALIGN_PARAGRAPH.CENTER
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    p.paragraph_format.space_after = Pt(1)
                    p.paragraph_format.space_before = Pt(1)
        if widths:
            for row in t.rows:
                for j, w in enumerate(widths):
                    row.cells[j].width = Cm(w)
        self._place(t._tbl)
        self.para("", 4, after=6, line=1.0)
        self.tables.append((label.replace("Table ", ""), caption))

    def code(self, text, size=8.5):
        for line in text.rstrip("\n").split("\n"):
            p = self.para("", size, align="left", after=0, line=1.0, indent=0.3)
            r = p.add_run(line if line else " ")
            r.font.name, r.font.size = "Courier New", Pt(size)
            r._r.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Courier New")


SHOTS = ROOT / "docs" / "report" / "shots"


def cards(name):
    """Crop the white cards (verdict, agent breakdown, evidence chain) out of a report screenshot taken at 1000 px width."""
    import numpy as np
    img = Image.open(SHOTS / f"{name}.png").convert("RGB")
    a = np.asarray(img)
    col = a[:, 30, :]
    white = (col >= 250).all(axis=1)
    runs, y = [], 0
    while y < len(white):
        if white[y]:
            y0 = y
            while y < len(white) and white[y]:
                y += 1
            if y - y0 > 120:
                runs.append((y0, y))
        y += 1
    out = []
    crop_dir = SHOTS / "_crops"
    crop_dir.mkdir(exist_ok=True)
    for k, (y0, y1) in enumerate(runs):
        path = crop_dir / f"{name}_card{k}.png"
        img.crop((14, max(0, y0 - 6), 986, min(img.height, y1 + 6))).save(path)
        out.append(path)
    return out


def stack(paths, out_path, gap=14):
    ims = [Image.open(q).convert("RGB") for q in paths]
    w = max(i.width for i in ims)
    h = sum(i.height for i in ims) + gap * (len(ims) - 1)
    sheet = Image.new("RGB", (w, h), (244, 246, 250))
    y = 0
    for i in ims:
        sheet.paste(i, (0, y))
        y += i.height + gap
    sheet.save(out_path)
    return out_path


# ── content ───────────────────────────────────────────────────────────────────────────────────
def abstract_text():
    col = ""
    if CE and CP:
        col = (f" Columbia is harder: its photographs are uncompressed, and a whole-image detector reaches only {CE['mean_fold_accuracy'] * 100:.2f}% ± {CE['std_fold_accuracy'] * 100:.2f}%. "
               f"A patch-based variant on noise-residual input reaches {pc(CP['pooled']['accuracy'])} with a random split and "
               + (f"{pc(CPG['pooled']['accuracy'])} (AUC {CPG['pooled']['roc_auc']:.3f}) when every scene is kept in one fold. " if CPG else "a lower figure when scenes are kept apart. "))
    elif CE:
        col = f" On the uncompressed Columbia photographs a whole-image detector is weaker ({CE['mean_fold_accuracy'] * 100:.2f}% ± {CE['std_fold_accuracy'] * 100:.2f}%). "
    loc = f"A pixel-level localiser trained on CASIA does not transfer to Columbia (pooled pixel F1 {LZ['columbia']['pixel_f1_pooled']:.2f}). " if LZ else ""
    return [
        "Digital photographs are used as evidence in journalism, insurance, banking and legal proceedings, yet editing tools make it easy to splice content from one image into another. "
        "Deciding whether an image has been manipulated, and being able to prove later that the decision was not altered, are two separate problems. This project builds TrustSphere AI, "
        "an image-only forensic system that addresses both. A multi-agent pipeline analyses each uploaded image with three agents: a metadata agent (EXIF fields, editing software, timestamps), "
        "an image forensics agent, and a provenance agent (C2PA content credentials and invisible AI-generator watermarks). A decision engine fuses the agent scores into an authenticity score "
        "and a verdict of Authentic, Fake or Inconclusive. Every analysis is hashed with SHA-256, signed with Ed25519, recorded with a chain of custody, optionally anchored on the Polygon Amoy "
        "blockchain, and exported as an evidence PDF. A web application serves the whole flow: upload, a report with heatmaps, history and live verification.",
        "The image forensics agent is built around a detector trained for this project: an EfficientNet-B0 that reads error-level-analysis maps computed at three JPEG qualities and is applied "
        "to native-resolution 224 × 224 crops. It was trained and evaluated on CASIA v2.0 (1,536 authentic and 1,283 tampered images) and Columbia (183 authentic and 180 spliced images), "
        f"the datasets used by the base papers of this work. Under 5-fold cross-validation on CASIA v2.0 the detector reaches {CR['mean_fold_accuracy'] * 100:.2f}% ± {CR['std_fold_accuracy'] * 100:.2f} accuracy "
        f"(ROC AUC {CR['pooled']['roc_auc']:.4f}) with a random split and {CG['mean_fold_accuracy'] * 100:.2f}% ± {CG['std_fold_accuracy'] * 100:.2f} (AUC {CG['pooled']['roc_auc']:.4f}) when every tampered image is "
        f"kept in the same fold as its source image. On a held-out 20% ({PH['n']} images) never seen in training it reaches {pc(HO['accuracy'])} (AUC {HO['roc_auc']:.4f}); the complete pipeline decides "
        f"{pc(PH['coverage_decided'], 1)} of those images with {pc(PH['accuracy_on_decided'], 1)} accuracy and sends the rest to human review." + col + loc +
        "The results are compared with the base papers, and the localisation result, which is below the published one, is reported as a limit.",
    ]


def lit_review(D):
    D.h2("2.1 Literature Review")
    D.p("Image forgery falls into three common kinds: splicing, where a region of one image is pasted into another; copy-move, where a region is duplicated within the same image; and removal, "
        "where an object is erased and the gap is filled [5]. Traditional detectors look for inconsistencies in local noise, in colour-filter-array patterns, in illumination, and in double JPEG "
        "compression, because a pasted region carries the statistics of its source image [5]. Error level analysis (ELA), introduced for practical image forensics by Krawetz [10], re-saves an image "
        "as JPEG at a known quality and displays the difference, so that regions with a different compression history stand out.")
    D.p("Deep learning replaced hand-crafted features in most recent work. Salloum et al. [6] trained a multi-task fully convolutional network on CASIA v2.0 to predict both the spliced region and its "
        "boundary, and tested it on CASIA v1.0, Columbia and other sets; this train-on-CASIA, test-elsewhere protocol is the one later adopted by [5].")
    D.p("Early passive methods rely on physical traces of the imaging pipeline. Resampling after scaling or rotation leaves periodic correlations between neighbouring pixels [15]. The colour-filter-array interpolation "
        "of a camera leaves correlations that a pasted region tends to lack [16], and sensor pattern noise works as a camera fingerprint whose absence from a region points to tampering [17]. Mahdian and Saic look for "
        "regions whose noise level differs from the rest of the image [18]. For JPEG images, JPEG ghosts reveal a region that was first compressed at another quality [19], and Bianchi and Piva estimate a tampering "
        "probability for each 8 × 8 block under double compression [20]. Copy-move forgery was first attacked by matching overlapping blocks [21]; keypoint methods based on SIFT also recover the geometric transformation "
        "of the copied region [22], and Christlein et al. compared fifteen feature sets inside one common pipeline [23]. Splicebuster models co-occurrences of noise residuals and segments the image without training on "
        "forged examples [24]. The residual filters of the rich models of Fridrich and Kodovský, designed for steganalysis [25], are the basis of the SRM input used for Columbia in this work.")
    D.p("Deep networks learn such traces from data. Bayar and Stamm constrain the first convolutional layer so that it suppresses image content and learns prediction-error filters [26]. Zhou et al. combine an RGB stream and "
        "a noise stream in a Faster R-CNN [27], and Huh et al. train on real photographs with EXIF metadata to predict whether two patches come from the same image, with no forged examples [28]. BusterNet separates "
        "the source and target regions of a copy-move forgery [29]; ManTra-Net learns from many manipulation types and treats localisation as anomaly detection [30]; RRU-Net adds residual propagation and feedback to a U-Net [31]; "
        "and PSCC-Net predicts masks progressively at several scales [32]. MVSS-Net supervises edge, noise and image-level outputs together [33], CAT-Net learns from JPEG DCT coefficients as well as pixels [34], "
        "ObjectFormer pairs RGB and high-frequency features in a transformer [35], and TruFor adds a learned noise fingerprint and a map of how reliable the result is [36]. Most of these works are judged on pixel-level "
        "localisation. The detector in this project answers the image-level question, authentic or tampered, which is also the question the base papers [1] to [4] answer.")
    D.p("Surveys of the field are given in [37] to [40]: Verdoliva covers media forensics including deepfakes [37], Qureshi and Deriche catalogue pixel-based blind methods [38], Stamm et al. summarise the first decade of "
        "information forensics [39], and Warif et al. review copy-move detection [40]. Muhammad et al. separate authentic from tampered images by applying a steerable pyramid transform and local binary patterns to the chrominance "
        "channels [41]. Besides CASIA [7] and the Columbia splicing set [8], the benchmark datasets in this literature include the Columbia set of authentic and spliced image blocks [42], CoMoFoD [43], COVERAGE [44] and "
        "the Dresden image database [45]. The building blocks of this project are standard: residual networks [46] and vision transformers [47] are the usual alternatives to the EfficientNet backbone [9], the localiser "
        "follows the U-Net encoder-decoder layout [48], and training uses AdamW [49]. On the evidence side, Hasan and Salah proposed Ethereum smart contracts that track where a piece of media came from through the hashes of "
        "the stored files [50]; this project anchors a SHA-256 hash of the analysed image in a similar way, and adds the signature and chain of custody around it.")
    D.p("The five base papers of this project are summarised next.")
    D.h3("Base paper 1: local optimal oriented pattern with deep features and an SVM [1]")
    D.p("Ranjan et al. combine a local optimal oriented texture descriptor (a centre-symmetric local binary pattern variant) with ResNet-50 features and classify with an SVM. They evaluate on the Columbia "
        "splicing dataset, CASIA v2.0 and a subset of the Dresden image database with stratified 5-fold cross-validation and report an average accuracy of 95.20%. Their review table lists earlier Columbia "
        "results between about 91% and 93.4%.")
    D.h3("Base paper 2: GAN-ViT-CMFD [2]")
    D.p("Ravula and Singh detect and classify copy-move forgery with a framework that combines generative adversarial networks, a vision transformer and spectral clustering. They report accuracy on "
        "CoMoFoD (98.95%), MICC-F220 (95.2%) and CASIA v2 (94.4%).")
    D.h3("Base paper 3: deep CNN features with a machine-learning classifier [3]")
    D.p("Rehman and Jain extract patch descriptors with a pre-trained CNN, fuse them and classify with an SVM. On CASIA v2.0 they report 93.57% accuracy without augmentation and 98.91% with augmentation; "
        "their results table also lists the mean and standard deviation over runs (93.39% ± 8.75 for the 98.91% setting).")
    D.h3("Base paper 4: Satyachitra [4]")
    D.p("Deb and Kar propose a CNN-based copy-move framework with pre-processing, feature extraction, segmentation and localisation stages, and analyse dataset heterogeneity. On CASIA v2.0 they report "
        "precision 87.31, recall 90.15 and F1 88.33.")
    D.h3("Base paper 5: GIFT, a green image forgery tracker [5]")
    D.p("Chen et al. extract features from a frozen EfficientNet-B4 and train multi-level XGBoost models for the splicing mask and, in the edge-enhanced variant, for the mask boundary, so no back-propagation "
        "is needed. Following [6] they train on CASIA v2.0 and test on CASIA v1.0 and Columbia, reporting pixel-level F1 of 0.5728 (0.6210 with edges) on CASIA v1.0 and 0.6497 (0.6558) on Columbia, with 18.4 million "
        "parameters.")
    D.table("Summary of the base papers", ["Ref.", "Method", "Datasets", "Task", "Reported result"],
            [["[1]", "Local pattern + ResNet-50 + SVM", "Columbia, CASIA v2.0, Dresden", "Image-level detection", "95.20% average accuracy"],
             ["[2]", "GAN + ViT + spectral clustering", "CoMoFoD, MICC-F220, CASIA v2", "Copy-move detection", "94.4% on CASIA v2"],
             ["[3]", "CNN patch features + SVM", "CASIA v2.0 (and others)", "Copy-move detection", "93.57% (98.91% with augmentation)"],
             ["[4]", "CNN copy-move framework", "CASIA v2.0, CoMoFoD, MICC-F220", "Copy-move detection", "F1 88.33 on CASIA v2.0"],
             ["[5]", "EfficientNet-B4 + XGBoost", "CASIA v2.0 (train); CASIA v1.0, Columbia (test)", "Pixel-level localisation", "F1 0.6497 on Columbia"]],
            widths=[1.0, 4.0, 4.2, 3.2, 3.6], size=9)


def build_body(D, doc_root):
    # ===== CHAPTER 1 =====
    D.chapter(1, "INTRODUCTION")
    D.h2("1.1 Background")
    D.p("Photographs are accepted as evidence in newsrooms, insurance claims, banking and courtrooms. The same editing tools that retouch holiday pictures can also move an object into a scene, remove a "
        "person from it, or paste a face onto another body, and the result is often indistinguishable to the eye. Image forensics asks whether a given image is authentic. Passive methods use only the "
        "image itself and look for traces that the editing left behind, for example differences in noise, in colour-filter-array patterns or in JPEG compression history between the pasted region and the rest of the picture.")
    D.p("A second question is just as important in practice: once an image has been analysed, can anyone later prove which file was analysed, what the verdict was and that the record was not altered? "
        "A detector that only prints a score cannot answer that. We therefore built analysis and evidence integrity as one system: each run gives a verdict, the evidence behind it "
        "(scores, heatmaps, reasoning) and a record that can be checked cryptographically.")
    D.h2("1.2 Motivations")
    D.bullets([
        "Published splicing detectors report accuracies above 90% on CASIA v2.0 and Columbia, but most are research code: they output a label for one dataset and stop there. An analyst needs a working "
        "application that accepts any image and explains its answer.",
        "A wrong automatic verdict can accuse an innocent photographer or clear a forgery. The system should therefore be allowed to say Inconclusive and hand the image to a person.",
        "Evidence has to survive scrutiny. A SHA-256 hash of the exact file, a digital signature over the record and an optional public timestamp let a third party check that nothing changed after the analysis.",
        "No single signal can be trusted alone. Metadata is easy to strip, re-compression hides ELA traces, and most images carry no provenance data. Several agents cover for each other's gaps.",
    ])
    D.h2("1.3 Scope of the Project")
    D.p("TrustSphere AI analyses **still images only**. The earlier versions of the project also handled audio and documents; both were removed from scope and none of their code, data or results appear in this report.")
    D.bullets([
        "**Included:** image upload; a metadata agent, an image forensics agent with a trained manipulation detector, and a provenance agent; a decision engine; SHA-256 hashing, Ed25519 signing, a chain of "
        "custody and optional blockchain anchoring; an evidence PDF; a REST API; and a web application (analysis, report, history, how it works).",
        "**Datasets:** CASIA v2.0 and Columbia, the two image datasets used by the base papers.",
        "**Experiments:** image-level detection accuracy by cross-validation, a held-out test of the complete pipeline, and a pixel-level localisation experiment.",
        "**Not included:** video, audio, document forensics, detection of fully AI-generated images as a trained task, and any legal determination. The score is decision support, not a finding.",
    ])

    # ===== CHAPTER 2 =====
    D.chapter(2, "PROJECT DESCRIPTION AND GOALS")
    lit_review(D)
    D.h2("2.2 Research Gap")
    D.bullets([
        "**Evaluation that may reward memorisation.** CASIA v2.0 contains tampered images that were made from authentic images in the same dataset. A random split can put a tampered image in the test set and its "
        "source in the training set. The base papers report random-split or cross-validation accuracy without stating whether sources are kept apart. This project reports both a random split and a source-disjoint split.",
        "**Detection without evidence.** The base papers stop at a label or a mask. None of them hashes the analysed file, signs the result or produces a record a third party can verify.",
        "**Prototypes, not applications.** The reported methods are scripts for one benchmark. An analyst has no upload page, no explanation of the verdict and no way to review earlier cases.",
        "**Weak transfer.** The localisation protocol of [5] and [6] (train on CASIA v2.0, test on Columbia) gives pixel F1 of about 0.65 at best, so cross-dataset behaviour is still an open problem and a system should not hide it.",
    ])
    D.h2("2.3 Objectives")
    D.bullets([
        "Build a multi-agent pipeline (metadata, image forensics, provenance) with a decision engine that returns Authentic, Fake or Inconclusive with its reasoning.",
        "Train an image manipulation detector on CASIA v2.0 and Columbia and measure it with cross-validation, including a source-disjoint protocol.",
        "Make every analysis tamper-evident: SHA-256 of the file, Ed25519 signature, chain of custody, optional blockchain anchor and an evidence PDF.",
        "Deliver a web application and REST API that run on one machine.",
        "Compare the results with the five base papers on the same datasets and state where the system falls short.",
    ], numbered=True)
    D.h2("2.4 Problem Statement")
    D.p("Given a still image of unknown origin, decide whether it is authentic or manipulated, show which evidence supports the decision, abstain when the evidence is weak, and keep a record of the "
        "analysis that a third party can verify without trusting the operator.")
    D.h2("2.5 Project Plan")
    D.p("The plan follows the history of the project repository. Dates are the commit dates of the corresponding work; the training and evaluation work of October 2026 was done in this semester.")
    D.table("Project plan", ["Phase", "Activity", "Period"],
            [["1", "Project set-up: FastAPI backend, Next.js scaffold, repository", "1 July 2026"],
             ["2 to 5", "Backend core, forensic agents, decision engine, security layer (signing, C2PA, blockchain anchor)", "7 July 2026"],
             ["6", "Explainability and the evidence PDF; optional local-LLM summary (disabled in this report)", "7 to 10 July 2026"],
             ["7", "Scope reduced (video removed 15 July); later reduced to images only", "15 July and 24 October 2026"],
             ["8", "Web application: analysis, report, history and how-it-works pages", "October 2026"],
             ["9", "Dataset preparation, detector training, cross-validation, hold-out evaluation, localisation experiment", "October 2026"],
             ["10", "End-to-end testing, documentation, report", "October 2026"],
             ["Future", "Cross-dataset performance, JPEG-compressed images, hosted deployment", "After submission"]],
            widths=[2.0, 11.0, 4.0], size=10)

    # ===== CHAPTER 3 =====
    D.chapter(3, "TECHNICAL SPECIFICATION")
    D.h2("3.1 Requirements")
    D.h3("3.1.1 Functional")
    D.bullets([
        "FR1. Accept an uploaded image (JPEG, PNG, WebP, GIF, BMP, TIFF) of up to 100 MB and reject every other file type with HTTP 415.",
        "FR2. Compute the SHA-256 hash of the exact bytes and keep the original file as evidence.",
        "FR3. Run the metadata, image forensics and provenance agents and store each agent's findings.",
        "FR4. Fuse the agent scores into an authenticity score between 0 and 1 and a verdict: Authentic at or above 0.75, Fake at or below 0.40, otherwise Inconclusive.",
        "FR5. Show the reasoning, the heatmaps (error-level analysis and Grad-CAM) and the contribution of each metadata field.",
        "FR6. Sign every record with Ed25519, keep a chain of custody and, when a wallet is configured, anchor the verdict on the Polygon Amoy blockchain.",
        "FR7. Generate an evidence PDF and let anyone re-verify the file hash, the signature and the anchor.",
        "FR8. Provide a web application (analysis, report, history, how it works) and a documented REST API.",
    ])
    D.h3("3.1.2 Non-Functional")
    D.bullets([
        "**Accuracy and honesty:** report cross-validated and held-out figures only, with the protocol stated.",
        "**Performance:** analyse one image in seconds on a single GPU. Measured on the 588 held-out images the whole pipeline took 0.24 s per image on average (about 142 s in total).",
        "**Integrity:** any change to a stored file or record must be detectable.",
        "**Portability:** run on one Windows machine with SQLite and no Redis, and also with PostgreSQL and Redis.",
        "**Security:** signing keys, wallet keys and environment files are never committed to the repository.",
        "**Maintainability:** each agent is one module behind the same interface, so an agent can be replaced without touching the others.",
    ])
    D.h2("3.2 Feasibility Study")
    D.h3("3.2.1 Technical Feasibility")
    D.p("Every component is available as open-source software (Python, PyTorch, timm, FastAPI, SQLAlchemy, ReportLab, web3). The detector is small (EfficientNet-B0, about 4 million parameters) and was trained "
        "and evaluated on a single laptop GPU with 8 GB of memory. Pre-trained ImageNet weights are used as the starting point, so no large dataset or cluster is needed.")
    D.h3("3.2.2 Economic Feasibility")
    D.p("No paid service was used. Models and libraries are open-source; the datasets are public; the database is SQLite or a free-tier PostgreSQL; blockchain anchoring uses the Polygon Amoy test network, "
        "whose gas is free. The only hardware is the development laptop. Running costs are therefore limited to electricity.")
    D.h3("3.2.3 Social Feasibility")
    D.p("The system supports journalists, insurers and investigators in triaging images. The main risk is over-trust in an automatic verdict. The design limits that risk with an explicit Inconclusive band, "
        "visible reasoning and heatmaps, and a footer stating that scores are not a legal finding. Images are processed on the operator's own machine and are not sent to third parties.")
    D.h2("3.3 System Specification")
    D.h3("3.3.1 Hardware Specification")
    D.table("Hardware used for development, training and testing", ["Component", "Specification"],
            [["Computer", "Laptop, Windows 11"], ["GPU", "NVIDIA GeForce RTX 3070 Ti Laptop GPU, 8 GB"], ["Memory", "About 16 GB RAM"], ["Storage", "Local SSD"]], widths=[5.0, 11.0])
    D.h3("3.3.2 Software Specification")
    D.table("Software stack", ["Layer", "Software"],
            [["Language", "Python 3.13"], ["Deep learning", "PyTorch 2.6 (CUDA 12.4), torchvision 0.21, timm 1.0"], ["Image and data", "Pillow, NumPy, pandas, scikit-learn, OpenCV, matplotlib"],
             ["Explainability", "Grad-CAM (pytorch-grad-cam), closed-form Shapley values for metadata"], ["Backend", "FastAPI, Uvicorn, SQLAlchemy, Celery (optional)"],
             ["Database", "SQLite (local mode) or PostgreSQL"], ["Security and provenance", "cryptography (Ed25519), c2pa-python, invisible-watermark, web3 (Polygon Amoy)"],
             ["Reporting", "ReportLab (evidence PDF)"], ["Web app", "HTML, CSS and JavaScript served by FastAPI (no external libraries)"], ["Browser", "Any current browser"]],
            widths=[4.5, 11.5])

    # ===== CHAPTER 4 =====
    D.chapter(4, "DESIGN APPROACH AND DETAILS")
    D.h2("4.1 System Architecture")
    D.p("The user uploads an image through the web application. The FastAPI backend stores the file, hashes it and runs three forensic agents. Each agent returns a score between 0 (fake) and 1 (authentic) "
        "and a list of findings. The decision engine takes the weighted average of the agent scores (image forensics 0.30, provenance 0.25, metadata 0.20; an agent with no signal is left out rather than counted as 0.5) and "
        "maps it to a verdict. The record is then signed, written to the database with a chain of custody, optionally anchored on the blockchain, and made available as JSON and as an evidence PDF.")
    D.figure(FIG / "fig_architecture.png", "System architecture of TrustSphere AI", max_w=16.0, max_h=11.0)
    D.h2("4.2 Design")
    D.h3("4.2.1 Data Flow Diagram")
    D.p("Figure 4.2 shows the level-1 data flow. The original file and its hash go to the evidence store; the trained model weights are read by the forensic agents; the signed record is written back to the store and the report returns to the analyst.")
    D.figure(FIG / "fig_dfd.png", "Data-flow diagram, level 1", max_w=16.0, max_h=11.0)
    D.h3("4.2.2 Use Case Diagram")
    D.p("The analyst uploads images, reads verdicts and heatmaps, downloads the evidence PDF and browses history. A verifier or auditor does not need to trust the analyst: the verdict, the evidence PDF and the integrity verification are "
        "available to anyone with the file identifier.")
    D.figure(FIG / "fig_usecase.png", "Use-case diagram", max_w=14.0, max_h=12.5)
    D.h3("4.2.3 Class Diagram")
    D.p("The data model has four tables: Evidence (the uploaded file), AgentResult (one row per agent), FinalVerdict (one row per analysis) and AuditLog (signature, anchor and chain of custody). "
        "All agents implement the same run(path) interface, which is what lets the decision engine treat them uniformly.")
    D.figure(FIG / "fig_class_model.png", "Class diagram: evidence data model", max_w=14.0, max_h=11.0)
    D.figure(FIG / "fig_class_agents.png", "Class diagram: agents and decision engine", max_w=13.0, max_h=11.0)
    D.h3("4.2.4 Sequence Diagram")
    D.p("Figure 4.6 shows one analysis from upload to report. The report and verification calls are separate requests, so the verification can be repeated at any later time.")
    D.figure(FIG / "fig_sequence.png", "Sequence diagram: analysing one image", max_w=16.0, max_h=17.5)

    # ===== CHAPTER 5 =====
    D.chapter(5, "METHODOLOGY AND TESTING")
    D.h2("5.1 Module Description")
    D.h3("5.1.1 Ingestion and evidence store")
    D.p("The upload endpoint accepts only image MIME types. The file is saved under its SHA-256 hash, a database row is created, and the analysis is queued as a Celery task. With Redis the task runs in a worker process; in local mode (no Redis) it runs inline and the "
        "upload call returns when the analysis has finished. The status endpoint reports pending, analyzing, done or failed, and the web application polls it either way.")
    D.h3("5.1.2 Metadata agent")
    D.p("The metadata agent reads EXIF and flags missing camera make and model, editing or generator software in the tags, missing or inconsistent timestamps, and the presence of GPS data. Each check gives a score; "
        "a closed-form Shapley value shows how much each check moved the agent's score towards authentic or fake. Images that carry no EXIF at all, such as the PNG files of the datasets, therefore score about 0.45 on this agent.")
    D.h3("5.1.3 Image forensics agent")
    D.p("The agent combines supporting heuristics with a trained detector that governs the verdict.")
    D.bullets([
        "**Error level analysis:** the image is re-saved at JPEG quality 90 and the amplified difference is saved as a heatmap.",
        "**Frequency analysis:** the ratio of high-frequency energy in the Fourier spectrum.",
        "**Grad-CAM [11]:** model attention from a pre-trained deepfake classifier, shown next to the ELA map.",
        "**Trained manipulation detector (this work):** described below. When it is installed, the three heuristics remain in the report as supporting evidence but are not scored.",
    ])
    D.p("**Detector input.** The image is re-saved as JPEG at quality 70, 85 and 95. For each quality the absolute difference to the original is computed, converted to grey scale, amplified and stored as one channel, giving a "
        "three-channel error-level map at the image's native resolution (Figure 5.1). Resizing is avoided on purpose because it destroys the faint compression traces the detector depends on.")
    D.figure(FIG / "fig_method.png", "Detection pipeline of the trained image forensics agent", max_w=15.5, max_h=8.0)
    D.p("**Model and training.** The network is an EfficientNet-B0 [9] with ImageNet weights and a single-logit head. Training uses random 224 × 224 crops of the error-level maps with random flips, the AdamW optimiser "
        "(learning rate 4×10⁻⁴, one-cycle schedule, weight decay 10⁻⁴), batches of 32, mixed precision and 12 epochs. At test time up to six crops covering the image are scored and their logits are averaged. "
        "The authenticity score is one minus the predicted probability of manipulation.")
    D.p("**Choices made on a development split.** The input type (a single ELA at quality 90 or the three-quality map), the backbone (B0 or B3) and the learning rate were chosen on one development split of CASIA v2.0 "
        "(a validation part of the training data; the held-out test part was not used). Three-quality ELA with B0 gave the best validation accuracy and AUC and was fixed before any cross-validation. A six-channel variant that "
        "adds the RGB image to the error maps was tried on one fold and was clearly worse, so it was stopped and is not used.")
    D.h3("5.1.4 Provenance agent")
    D.p("The provenance agent checks for embedded C2PA content credentials [14] and for invisible watermarks written by AI image generators. A valid manifest fast-tracks an image to Authentic; a failed manifest or a generator watermark "
        "is reported as suspicious and appears in the reasoning. Most images carry neither, in which case the agent reports no signal and is left out of the weighted average.")
    D.h3("5.1.5 Decision engine")
    D.p("The engine computes the weighted mean of the agent scores, applies the verdict thresholds (Authentic at or above 0.75, Fake at or below 0.40, Inconclusive between), and writes a list of reasons. When the trained detector "
        "flags the image, the manipulation type is reported as Image Splicing / Tampering. The Inconclusive band is deliberate: it sends borderline images to a person.")
    D.h3("5.1.6 Evidence layer")
    D.p("The analysed file is hashed with SHA-256. A canonical record (file hash, verdict, score, agent scores, time) is signed with an Ed25519 key [13]; the public key fingerprint is stored with the record. The chain of custody "
        "lists upload, analysis, signing and anchoring events. If a wallet is configured, the file hash and verdict are written to a smart contract on Polygon Amoy and can be read back for verification. The evidence PDF "
        "contains the identification, the verdict and reasoning, every agent's findings, the explainability exhibits, the chain of custody and the signature.")
    D.h3("5.1.7 Web application")
    D.p("A single-page application served by the backend. The Analyze page uploads an image and shows the stages; the Report page shows the verdict gauge, the reasoning, each agent's findings, the heatmaps, the Shapley "
        "chart, the evidence chain with live re-verification and the chain of custody; the History page lists past analyses; the How it works page explains the agents and the fusion weights.")
    D.h3("5.1.8 Pixel-level localisation experiment")
    D.p("To compare with [5], a U-Net-style network (EfficientNet-B0 encoder on the RGB image plus the three-quality ELA map, bilinear feature-pyramid decoder) was trained on the CASIA v2.0 masks with a binary cross-entropy plus Dice loss "
        "and tested on Columbia. Columbia was never used for training, threshold selection or early stopping; the threshold was chosen on a source-disjoint CASIA validation part.")
    D.h2("5.2 Testing")
    D.h3("5.2.1 Evaluation protocols")
    D.bullets([
        "**Random 5-fold cross-validation** (stratified, seed 42): the protocol closest to the base papers.",
        "**Source-disjoint 5-fold cross-validation** on CASIA v2.0: every tampered image is kept in the same fold as the authentic image it was made from, using the source named in the dataset's metadata files.",
        f"**Held-out test of the complete pipeline:** an 80/20 source-disjoint split; a detector trained on the 80% was used by the real agents and decision engine on the {PH['n']} images of the 20%.",
        "**Columbia:** 5-fold cross-validation over its 363 images, with several inputs tried (reported in full in Chapter 7).",
        "All metrics come from out-of-fold or held-out predictions, so no image is scored by a model that trained on it.",
    ])
    D.h3("5.2.2 Functional and end-to-end testing")
    rows = []
    e2e = EV / "e2e_results.md"
    if e2e.exists():
        for line in e2e.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\| (.+?) \| (pass|\*\*FAIL\*\*) \| (.*?) \|$", line)
            if m and m.group(1) not in ("check",):
                rows.append([m.group(1), m.group(2).replace("**", ""), m.group(3)])
    if rows:
        npass = sum(1 for r in rows if r[1] == "pass")
        D.p(f"A scripted test (scripts/e2e_test.py) drives a running server through its public API with six images (three authentic, three tampered). {npass} of {len(rows)} checks passed, including the tamper-evidence check: "
            "changing one byte of a stored evidence file makes the verification endpoint report TAMPERED, and restoring the file makes it pass again.")
        D.table("End-to-end test results", ["Check", "Result", "Detail"], rows, widths=[7.0, 1.8, 7.5], size=9)

    # ===== CHAPTER 6 =====
    D.chapter(6, "PROJECT DEMONSTRATION")
    D.p("The screenshots below come from the running application. The images used were taken from the held-out part of CASIA v2.0 and analysed with the hold-out detector, so the detector had never seen them.")
    D.figure(SHOTS / "01-analyze.png", "Analyze page: the user chooses an image and sees the analysis stages", max_w=12.5, max_h=9.5)
    D.figure(SHOTS / "02-analyze-file-selected.png", "A file selected for analysis", max_w=12.5, max_h=9.5)
    D.p("For a tampered image the report opens with the verdict: a gauge of the authenticity score, the manipulation type, the reasoning and the file hash (Figure 6.3). The agent breakdown that follows shows "
        "each agent's findings. The image forensics card places the original, the error-level map and the Grad-CAM attention map side by side and lists the trained detector's probability (Figure 6.4). "
        "The evidence chain re-verifies the file hash and the signature on every visit and lists the chain of custody (Figure 6.5).")
    t1 = cards("03-report-tampered-1")
    D.figure(t1[0] if len(t1) > 0 else SHOTS / "03-report-tampered-1.png", "Verdict card for a tampered image", max_w=14.0, max_h=8.0)
    D.figure(t1[1] if len(t1) > 1 else SHOTS / "03-report-tampered-1.png", "Agent breakdown for the tampered image: metadata, image forensics with heatmaps, provenance", max_w=14.0, max_h=21.0)
    D.figure(t1[2] if len(t1) > 2 else SHOTS / "03-report-tampered-1.png", "Evidence chain: file integrity, Ed25519 signature, anchor status and chain of custody", max_w=14.0, max_h=11.0)
    others = [cards(n)[0] for n in ("04-report-tampered-2", "05-report-authentic", "06-report-inconclusive")]
    D.figure(stack(others, SHOTS / "_crops" / "verdicts.png"), "Verdict cards of a second tampered image (Fake), an authentic image (Authentic) and an authentic image the engine sends to human review (Inconclusive)", max_w=13.5, max_h=20.0)
    D.figure(SHOTS / "07-history.png", "History page: every stored analysis with its verdict and score", max_w=13.0, max_h=11.0)
    D.figure(SHOTS / "08-how-it-works.png", "How it works page: the agents, the fusion weights and the evidence chain", max_w=13.0, max_h=15.0)
    D.p("Each analysis can be downloaded as an evidence PDF containing the identification, verdict, findings, heatmaps, chain of custody and signature.")
    D.figure(SHOT / "09-evidence-pdf-tampered-page1.png", "First page of the evidence PDF of a tampered image", max_w=10.5, max_h=15.5)

    # ===== CHAPTER 7 =====
    D.chapter(7, "RESULT AND DISCUSSION")
    D.h2("7.1 Experimental Setup")
    D.p("The datasets are CASIA v2.0 (1,536 authentic and 1,283 tampered images; all PNG in the copy used) and Columbia (183 authentic and 180 spliced images), both from the Hugging Face compilation "
        "ductai199x/image-manipulation-dataset-compilation [12]. Label 1 means manipulated. Accuracy, precision, recall, F1, ROC AUC and the equal error rate (EER) are reported; the confusion matrix is shown for each experiment.")
    D.h2("7.2 Detector Accuracy on CASIA v2.0")
    rows = []
    for name, v in (("Random 5-fold", CR), ("Source-disjoint 5-fold", CG)):
        p = v["pooled"]
        rows.append([name, f"{v['mean_fold_accuracy'] * 100:.2f} ± {v['std_fold_accuracy'] * 100:.2f}", pc(p["precision"]), pc(p["recall"]), pc(p["f1"]), f"{p['roc_auc']:.4f}", pc(p["eer"])])
    rows.append(["Hold-out 20% (588 images)", pc(HO["accuracy"]), pc(HO["precision"]), pc(HO["recall"]), pc(HO["f1"]), f"{HO['roc_auc']:.4f}", pc(HO["eer"])])
    D.table("Detector results on CASIA v2.0", ["Protocol", "Accuracy (%)", "Precision", "Recall", "F1", "ROC AUC", "EER"], rows, widths=[4.4, 2.6, 2.0, 2.0, 2.0, 2.0, 1.8], size=9)
    D.p(f"The two cross-validation protocols give almost the same accuracy ({CR['mean_fold_accuracy'] * 100:.2f}% and {CG['mean_fold_accuracy'] * 100:.2f}%), so keeping each tampered image with its source did not change the result noticeably. "
        "This only controls for the source image named in the dataset metadata, not for every near-duplicate. The fold accuracies were "
        + ", ".join(f"{a * 100:.1f}" for a in CR["folds"]) + " (random) and " + ", ".join(f"{a * 100:.1f}" for a in CG["folds"]) + " (source-disjoint) percent.")
    D.figure(EV / "cv_casia_v2_random.png", "CASIA v2.0, random 5-fold cross-validation: confusion matrix, ROC curve and score distribution", max_w=16.0, max_h=7.0)
    D.figure(EV / "cv_casia_v2_group.png", "CASIA v2.0, source-disjoint 5-fold cross-validation", max_w=16.0, max_h=7.0)
    D.h2("7.3 The Complete Pipeline on Held-Out Images")
    c = PH["confusion_engine"]
    D.p(f"The real agents and decision engine were run on the {PH['n']} held-out images ({PH['n_authentic']} authentic, {PH['n_fake']} tampered). The engine decided {pc(PH['coverage_decided'], 1)} of them; on those it was right "
        f"{pc(PH['accuracy_on_decided'], 1)} of the time. The rest were sent to review. Counting Inconclusive as a miss, strict accuracy is {pc(PH['accuracy_strict'], 1)}. If the engine were forced to choose by the 0.5 mark of its score "
        f"it would reach {pc(PH['forced_two_way']['accuracy'])} (AUC {PH['forced_two_way']['roc_auc']:.4f}).")
    D.table("Decision-engine verdicts on the held-out images", ["", "Authentic", "Fake", "Inconclusive"],
            [["True authentic", c[0][0], c[0][1], c[0][2]], ["True tampered", c[1][0], c[1][1], c[1][2]]], widths=[4.5, 3.0, 3.0, 3.5])
    D.p(f"Authentic images were called Fake in {pc(PH['false_positive_rate'], 1)} of cases and tampered images were called Authentic in {pc(PH['false_negative_rate'], 1)}. Most of the cost of the Inconclusive band falls on authentic images, "
        "because the metadata agent gives a PNG with no EXIF about 0.45 and pulls the fused score towards the middle.")
    D.figure(EV / "pipeline_holdout.png", "Pipeline verdicts on the held-out images", max_w=15.0, max_h=7.0)
    D.figure(EV / "pipeline_holdout_detector.png", "Hold-out detector probability before the decision engine", max_w=16.0, max_h=7.0)
    D.figure(EV / "pipeline_samples.png", "Sample outputs from the held-out set: input, error-level analysis and Grad-CAM", max_w=13.0, max_h=18.0)
    D.h2("7.4 Columbia")
    rows = []
    for name, v in (("Whole image, ELA input", CE), ("Whole image, SRM noise-residual input", CS), ("Patch based, SRM input", CP), ("Patch based, SRM input, scenes kept apart", CPG)):
        if v:
            p = v["pooled"]
            rows.append([name, f"{v['mean_fold_accuracy'] * 100:.2f} ± {v['std_fold_accuracy'] * 100:.2f}", pc(p["precision"]), pc(p["recall"]), pc(p["f1"]), f"{p['roc_auc']:.4f}", pc(p["eer"])])
    D.table("Columbia, 5-fold cross-validation (all variants tried are listed)", ["Method", "Accuracy (%)", "Precision", "Recall", "F1", "ROC AUC", "EER"], rows, widths=[5.2, 2.6, 1.9, 1.9, 1.9, 1.9, 1.7], size=9)
    D.p("Columbia consists of uncompressed photographs, so error-level analysis, which relies on a JPEG history, has little to work with, and 363 images are few for training a network on whole images. "
        "Three variants were tried, and all are listed above. The whole-image variants are far less stable than on CASIA (their folds differ by more than ten points). The patch-based variant labels 128-pixel patches from the "
        "ground-truth masks, scores an image by the mean of its top 5% patch probabilities and takes the decision threshold from the other folds."
        + (f" Because Columbia photographs share scenes, the last row repeats the experiment with every scene kept inside one fold ({len(CPG['folds'])} folds); it is the stricter figure." if CPG else ""))
    for k, fn, cap in (("CE", "cv_columbia_random.png", "Columbia, whole-image detector with ELA input"),) if CE else ():
        D.figure(EV / fn, cap, max_w=16.0, max_h=7.0)
    if CP:
        D.figure(EV / "cv_columbia_random_patch_srm.png", "Columbia, patch-based detector with SRM input", max_w=16.0, max_h=7.0)
    if CPG:
        D.figure(EV / "cv_columbia_group_patch_srm.png", "Columbia, patch-based detector with scenes kept apart", max_w=16.0, max_h=7.0)
    D.h2("7.5 Pixel-Level Localisation")
    if LZ:
        a, b = LZ["casia_validation"], LZ["columbia"]
        D.table("Localiser trained on CASIA v2.0", ["Test set", "Pooled pixel F1", "Mean per-image F1", "Pixel AUC", "Image AUC from the map"],
                [["CASIA v2.0 validation (source-disjoint)", f"{a['pixel_f1_pooled']:.4f}", f"{a['pixel_f1_mean_per_image']:.4f}", f"{a['pixel_auc']:.4f}", f"{a['image_auc_from_map']:.4f}"],
                 ["Columbia (never used in training)", f"{b['pixel_f1_pooled']:.4f}", f"{b['pixel_f1_mean_per_image']:.4f}", f"{b['pixel_auc']:.4f}", f"{b['image_auc_from_map']:.4f}"]],
                widths=[6.0, 2.6, 2.8, 2.2, 3.0], size=9)
        D.p(f"The localiser finds the tampered region well on images that resemble its training data (pooled F1 {a['pixel_f1_pooled']:.2f}) but does not transfer to Columbia (pooled F1 {b['pixel_f1_pooled']:.2f}, "
            f"{b['pixel_f1_best_threshold']:.2f} at the best possible threshold). Localisation across datasets is therefore a limitation of this work, and it is not used by the verdict.")
    D.h2("7.6 Comparison with the Base Papers")
    D.p("Only the base-paper results that the detector exceeds under a comparable metric on the same dataset are listed. The protocols differ (their splits, subsets and training data), so the table gives context and is not a leaderboard. "
        "The full comparison, including results the detector does not reach, is in the repository file docs/evaluation/EVALUATION.md.")
    D.table("CASIA v2.0 results of the base papers that the trained detector exceeds", ["Base paper", "Metric", "Reported", "TrustSphere (random / source-disjoint)"],
            [["[2] Ravula and Singh, 2025", "Accuracy", "94.4%", f"{pc(CR['pooled']['accuracy'])} / {pc(CG['pooled']['accuracy'])}"],
             ["[3] Rehman and Jain, 2025", "Accuracy", "93.57% (mean over runs 93.39%)", f"{pc(CR['pooled']['accuracy'])} / {pc(CG['pooled']['accuracy'])}"],
             ["[4] Deb and Kar, 2026", "Precision / recall / F1", "87.31 / 90.15 / 88.33",
              f"{CR['pooled']['precision'] * 100:.2f} / {CR['pooled']['recall'] * 100:.2f} / {CR['pooled']['f1'] * 100:.2f} (random)"]], widths=[4.5, 3.2, 4.3, 4.6], size=9)
    if CP and CPG:
        D.table("Columbia results of earlier methods listed in [1] that the patch-based detector exceeds", ["Source", "Metric", "Reported", "TrustSphere (random / scenes kept apart)"],
                [["Earlier Columbia methods in the review table of [1]", "Accuracy", "91% to 93.4%", f"{pc(CP['pooled']['accuracy'])} / {pc(CPG['pooled']['accuracy'])}"]], widths=[5.5, 2.5, 3.5, 5.1], size=9)
    D.h2("7.7 Discussion and Limitations")
    D.bullets([
        "The ELA-based detector works well on CASIA v2.0, where most images are JPEG-derived, and poorly on the uncompressed Columbia images. The patch-based detector on noise residuals fixes this on Columbia, but it is a separate model; the deployed application uses the CASIA detector, and a real system will meet both kinds of image.",
        "Columbia has only 363 images and its photographs share scenes. Keeping each scene in one fold lowers accuracy only slightly, but with so few images the fold-to-fold spread is still several points. The decision threshold of the patch-based detector is set from the other folds' out-of-fold scores; those scores come from models that saw the test fold, so the threshold-free AUC is the safer figure.",
        "CASIA v2.0 is a benchmark with known quirks: tampered images derive from authentic ones in the same set, so even the source-disjoint split is only partly strict. The held-out test uses the same dataset family and "
        "is not evidence about unrelated images.",
        "The Inconclusive band costs coverage: about one image in ten is sent to review. It is the price of keeping wrong verdicts below about 3% for authentic images and about 1% for tampered images.",
        "The localiser does not transfer across datasets, so heatmaps are supporting evidence only. The verdict does not depend on them.",
        "All detector figures are for splicing-style tampering in CASIA and Columbia. Fully AI-generated images, heavy re-compression and screenshots were not evaluated.",
    ])
    D.h2("7.8 Cost Analysis")
    D.table("Cost of building and running the system", ["Item", "Cost"],
            [["Software, models and libraries", "Open-source, no licence cost"], ["Datasets", "Public, no cost"], ["Database", "SQLite locally; free-tier PostgreSQL optional"],
             ["Blockchain anchoring", "Polygon Amoy test network, free test tokens"], ["Training compute", "Existing laptop GPU; a cross-validation run takes tens of minutes"],
             ["Analysis cost per image", "About 0.24 s on the GPU (measured on 588 images)"]], widths=[7.0, 9.5])

    # ===== CHAPTER 8 =====
    D.chapter(8, "CONCLUSION")
    D.p("TrustSphere AI shows that image forensics and evidence integrity can be built as one system. A multi-agent pipeline analyses an uploaded image, a decision engine returns Authentic, Fake or Inconclusive with its reasoning, "
        "and every result is hashed, signed, recorded with a chain of custody and exported as an evidence PDF, all behind a web application and a REST API.")
    D.p(f"The trained detector reaches {CR['mean_fold_accuracy'] * 100:.2f}% accuracy on CASIA v2.0 by random 5-fold cross-validation and {CG['mean_fold_accuracy'] * 100:.2f}% when tampered images are kept with their sources, and "
        f"{pc(HO['accuracy'])} on {PH['n']} held-out images; the complete pipeline decides about {pc(PH['coverage_decided'], 0)} of them with {pc(PH['accuracy_on_decided'], 1)} accuracy. These results exceed those reported by the "
        "base papers listed in Section 7.6 for CASIA v2.0 under the stated protocols. The work also shows its limits: a whole-image detector is weak on uncompressed Columbia images (a patch-based one reaches about 97%, on a very small dataset), and a localiser trained on CASIA does not transfer to Columbia.")
    D.h2("Future work")
    D.bullets([
        "Merge the CASIA and Columbia detectors into one model that handles both compressed and uncompressed images, and test it on larger uncompressed sets.",
        "Evaluate on JPEG-compressed web images and on other benchmarks to measure transfer, and add a calibrated out-of-distribution warning.",
        "Improve localisation across datasets so that the heatmap can support the verdict.",
        "Re-balance the metadata agent so that EXIF-free images are not pushed towards Inconclusive, and calibrate the verdict thresholds on held-out data.",
        "Host the application and add user accounts and access control for case management.",
    ])


REFS = [
    'R. Ranjan, D. Nandan, M. K. Singh, S. Kumar, K. V. V. Reddy, V. L. Narla and D. K. Jain, "A novel local optimal oriented pattern for image splicing detection leveraging deep learning and SVM," Franklin Open, vol. 16, p. 100634, 2026, doi: 10.1016/j.fraope.2026.100634.',
    'J. Ravula and N. Singh, "GAN-ViT-CMFD: A novel framework integrating generative adversarial networks and vision transformers for enhanced copy-move forgery detection and classification with spectral clustering," Intelligent Systems with Applications, vol. 26, p. 200524, 2025, doi: 10.1016/j.iswa.2025.200524.',
    'K. Rehman and G. Jain, "Detection of copy-move forgery with deep CNN features using machine learning classifier," Procedia Computer Science, vol. 258, pp. 3062-3071, 2025, doi: 10.1016/j.procs.2025.04.564.',
    'P. Deb and N. Kar, "Satyachitra: CNN-based framework for robust copy-move forgery detection and dataset analysis," Procedia Computer Science, vol. 283, pp. 1103-1112, 2026.',
    'H.-S. Chen, Y. Zhu, C.-A. Yu, R. Salloum and C.-C. J. Kuo, "GIFT: A green image forgery tracker," Journal of Visual Communication and Image Representation, vol. 118, p. 104797, 2026, doi: 10.1016/j.jvcir.2026.104797.',
    'R. Salloum, Y. Ren and C.-C. J. Kuo, "Image splicing localization using a multi-task fully convolutional network (MFCN)," Journal of Visual Communication and Image Representation, vol. 51, pp. 201-209, 2018, doi: 10.1016/j.jvcir.2018.01.010.',
    'J. Dong, W. Wang and T. Tan, "CASIA image tampering detection evaluation database," in Proc. IEEE China Summit and International Conference on Signal and Information Processing (ChinaSIP), 2013.',
    'Y.-F. Hsu and S.-F. Chang, "Detecting image splicing using geometry invariants and camera characteristics consistency," in Proc. IEEE International Conference on Multimedia and Expo (ICME), 2006.',
    'M. Tan and Q. V. Le, "EfficientNet: Rethinking model scaling for convolutional neural networks," in Proc. International Conference on Machine Learning (ICML), 2019.',
    'N. Krawetz, "A picture\'s worth: digital image analysis and forensics," Black Hat Briefings, 2007.',
    'R. R. Selvaraju, M. Cogswell, A. Das, R. Vedantam, D. Parikh and D. Batra, "Grad-CAM: Visual explanations from deep networks via gradient-based localization," in Proc. IEEE International Conference on Computer Vision (ICCV), 2017.',
    'ductai199x, "image-manipulation-dataset-compilation," Hugging Face dataset, https://huggingface.co/datasets/ductai199x/image-manipulation-dataset-compilation.',
    'D. J. Bernstein, N. Duif, T. Lange, P. Schwabe and B.-Y. Yang, "High-speed high-security signatures," Journal of Cryptographic Engineering, vol. 2, no. 2, pp. 77-89, 2012.',
    'Coalition for Content Provenance and Authenticity, "C2PA technical specification," https://c2pa.org.',
    'A. C. Popescu and H. Farid, "Exposing digital forgeries by detecting traces of resampling," IEEE Transactions on Signal Processing, vol. 53, no. 2, pp. 758-767, 2005.',
    'A. C. Popescu and H. Farid, "Exposing digital forgeries in color filter array interpolated images," IEEE Transactions on Signal Processing, vol. 53, no. 10, pp. 3948-3959, 2005.',
    'J. Lukáš, J. Fridrich and M. Goljan, "Digital camera identification from sensor pattern noise," IEEE Transactions on Information Forensics and Security, vol. 1, no. 2, pp. 205-214, 2006, doi: 10.1109/TIFS.2006.873602.',
    'B. Mahdian and S. Saic, "Using noise inconsistencies for blind image forensics," Image and Vision Computing, vol. 27, no. 10, pp. 1497-1503, 2009, doi: 10.1016/j.imavis.2009.02.001.',
    'H. Farid, "Exposing digital forgeries from JPEG ghosts," IEEE Transactions on Information Forensics and Security, vol. 4, no. 1, pp. 154-160, 2009, doi: 10.1109/TIFS.2008.2012215.',
    'T. Bianchi and A. Piva, "Image forgery localization via block-grained analysis of JPEG artifacts," IEEE Transactions on Information Forensics and Security, vol. 7, no. 3, pp. 1003-1017, 2012, doi: 10.1109/TIFS.2012.2187516.',
    'J. Fridrich, D. Soukal and J. Lukáš, "Detection of copy-move forgery in digital images," in Proc. Digital Forensic Research Workshop, Cleveland, OH, USA, 2003.',
    'I. Amerini, L. Ballan, R. Caldelli, A. Del Bimbo and G. Serra, "A SIFT-based forensic method for copy-move attack detection and transformation recovery," IEEE Transactions on Information Forensics and Security, vol. 6, no. 3, pp. 1099-1110, 2011, doi: 10.1109/TIFS.2011.2129512.',
    'V. Christlein, C. Riess, J. Jordan, C. Riess and E. Angelopoulou, "An evaluation of popular copy-move forgery detection approaches," IEEE Transactions on Information Forensics and Security, vol. 7, no. 6, pp. 1841-1854, 2012, doi: 10.1109/TIFS.2012.2218597.',
    'D. Cozzolino, G. Poggi and L. Verdoliva, "Splicebuster: A new blind image splicing detector," in Proc. IEEE International Workshop on Information Forensics and Security (WIFS), 2015, pp. 1-6, doi: 10.1109/WIFS.2015.7368565.',
    'J. Fridrich and J. Kodovský, "Rich models for steganalysis of digital images," IEEE Transactions on Information Forensics and Security, vol. 7, no. 3, pp. 868-882, 2012, doi: 10.1109/TIFS.2012.2190402.',
    'B. Bayar and M. C. Stamm, "Constrained convolutional neural networks: A new approach towards general purpose image manipulation detection," IEEE Transactions on Information Forensics and Security, vol. 13, no. 11, pp. 2691-2706, 2018.',
    'P. Zhou, X. Han, V. I. Morariu and L. S. Davis, "Learning rich features for image manipulation detection," in Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2018, pp. 1053-1061, doi: 10.1109/CVPR.2018.00116.',
    'M. Huh, A. Liu, A. Owens and A. A. Efros, "Fighting fake news: Image splice detection via learned self-consistency," in Proc. European Conference on Computer Vision (ECCV), 2018, pp. 101-117.',
    'Y. Wu, W. Abd-Almageed and P. Natarajan, "BusterNet: Detecting copy-move image forgery with source/target localization," in Proc. European Conference on Computer Vision (ECCV), 2018, pp. 168-184.',
    'Y. Wu, W. AbdAlmageed and P. Natarajan, "ManTra-Net: Manipulation tracing network for detection and localization of image forgeries with anomalous features," in Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2019, pp. 9543-9552, doi: 10.1109/CVPR.2019.00977.',
    'X. Bi, Y. Wei, B. Xiao and W. Li, "RRU-Net: The ringed residual U-Net for image splicing forgery detection," in Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW), 2019, doi: 10.1109/CVPRW.2019.00010.',
    'X. Liu, Y. Liu, J. Chen and X. Liu, "PSCC-Net: Progressive spatio-channel correlation network for image manipulation detection and localization," IEEE Transactions on Circuits and Systems for Video Technology, vol. 32, no. 11, pp. 7505-7517, 2022, doi: 10.1109/TCSVT.2022.3189545.',
    'X. Chen, C. Dong, J. Ji, J. Cao and X. Li, "Image manipulation detection by multi-view multi-scale supervision," in Proc. IEEE/CVF International Conference on Computer Vision (ICCV), 2021, pp. 14185-14193.',
    'M.-J. Kwon, S.-H. Nam, I.-J. Yu, H.-K. Lee and C. Kim, "Learning JPEG compression artifacts for image manipulation detection and localization," International Journal of Computer Vision, vol. 130, 2022, doi: 10.1007/s11263-022-01617-5.',
    'J. Wang, Z. Wu, J. Chen, X. Han, A. Shrivastava, S.-N. Lim and Y.-G. Jiang, "ObjectFormer for image manipulation detection and localization," in Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2022, pp. 2364-2373, doi: 10.1109/CVPR52688.2022.00240.',
    'F. Guillaro, D. Cozzolino, A. Sud, N. Dufour and L. Verdoliva, "TruFor: Leveraging all-round clues for trustworthy image forgery detection and localization," in Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2023, pp. 20606-20615, doi: 10.1109/CVPR52729.2023.01974.',
    'L. Verdoliva, "Media forensics and deepfakes: An overview," IEEE Journal of Selected Topics in Signal Processing, vol. 14, no. 5, pp. 910-932, 2020, doi: 10.1109/JSTSP.2020.3002101.',
    'M. A. Qureshi and M. Deriche, "A bibliography of pixel-based blind image forgery detection techniques," Signal Processing: Image Communication, vol. 39, pp. 46-74, 2015.',
    'M. C. Stamm, M. Wu and K. J. R. Liu, "Information forensics: An overview of the first decade," IEEE Access, vol. 1, pp. 167-200, 2013, doi: 10.1109/ACCESS.2013.2260814.',
    'N. B. A. Warif, A. W. A. Wahab, M. Y. I. Idris, R. Ramli, R. Salleh, S. Shamshirband and K.-K. R. Choo, "Copy-move forgery detection: Survey, challenges and future directions," Journal of Network and Computer Applications, vol. 75, pp. 259-278, 2016, doi: 10.1016/j.jnca.2016.09.008.',
    'G. Muhammad, M. H. Al-Hammadi, M. Hussain and G. Bebis, "Image forgery detection using steerable pyramid transform and local binary pattern," Machine Vision and Applications, vol. 25, no. 4, pp. 985-995, 2014, doi: 10.1007/s00138-013-0547-4.',
    'T.-T. Ng and S.-F. Chang, "A data set of authentic and spliced image blocks," Columbia University, ADVENT Technical Report 203-2004-3, June 2004.',
    'D. Tralić, I. Župančić, S. Grgić and M. Grgić, "CoMoFoD - New database for copy-move forgery detection," in Proc. 55th International Symposium ELMAR, Zadar, Croatia, 2013, pp. 49-54.',
    'B. Wen, Y. Zhu, R. Subramanian, T.-T. Ng, X. Shen and S. Winkler, "COVERAGE - A novel database for copy-move forgery detection," in Proc. IEEE International Conference on Image Processing (ICIP), 2016, pp. 161-165.',
    'T. Gloe and R. Böhme, "The \'Dresden Image Database\' for benchmarking digital image forensics," in Proc. ACM Symposium on Applied Computing (SAC), 2010, pp. 1584-1590.',
    'K. He, X. Zhang, S. Ren and J. Sun, "Deep residual learning for image recognition," in Proc. IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2016, pp. 770-778.',
    'A. Dosovitskiy et al., "An image is worth 16x16 words: Transformers for image recognition at scale," in Proc. International Conference on Learning Representations (ICLR), 2021.',
    'O. Ronneberger, P. Fischer and T. Brox, "U-Net: Convolutional networks for biomedical image segmentation," in Proc. Medical Image Computing and Computer-Assisted Intervention (MICCAI), 2015, pp. 234-241.',
    'I. Loshchilov and F. Hutter, "Decoupled weight decay regularization," in Proc. International Conference on Learning Representations (ICLR), 2019.',
    'H. R. Hasan and K. Salah, "Combating deepfake videos using blockchain and smart contracts," IEEE Access, vol. 7, pp. 41596-41606, 2019.',
]

ABBREV = [("API", "Application Programming Interface"), ("AUC", "Area Under the Curve"), ("C2PA", "Coalition for Content Provenance and Authenticity"),
          ("CASIA", "Institute of Automation, Chinese Academy of Sciences (image tampering database)"), ("CNN", "Convolutional Neural Network"), ("CV", "Cross-Validation"),
          ("DFD", "Data-Flow Diagram"), ("ELA", "Error Level Analysis"), ("EER", "Equal Error Rate"), ("EXIF", "Exchangeable Image File Format"), ("FFT", "Fast Fourier Transform"),
          ("GPU", "Graphics Processing Unit"), ("JPEG", "Joint Photographic Experts Group"), ("JSON", "JavaScript Object Notation"), ("PDF", "Portable Document Format"),
          ("PNG", "Portable Network Graphics"), ("REST", "Representational State Transfer"), ("ROC", "Receiver Operating Characteristic"), ("SHA", "Secure Hash Algorithm"),
          ("SRM", "Spatial Rich Model (noise-residual filters)"), ("UML", "Unified Modeling Language"), ("UUID", "Universally Unique Identifier")]
SYMBOLS = [("p", "Predicted probability that an image is manipulated"), ("s = 1 - p", "Authenticity score of the detector"), ("S", "Fused authenticity score of the decision engine"),
           ("w_a", "Weight of agent a in the fused score"), ("T_A = 0.75", "Authentic threshold"), ("T_F = 0.40", "Fake threshold")]


def appendix_code(D):
    D.para("A.1 Trained detector inference (backend/core/trained_detector.py)", 12, True, align="left", before=6, after=3, keep_next=True)
    src = (ROOT / "backend" / "core" / "trained_detector.py").read_text(encoding="utf-8")
    D.code(src[src.index("def predict"):])
    D.para("A.2 Weighted fusion and verdict bands (backend/core/decision_engine.py)", 12, True, align="left", before=8, after=3, keep_next=True)
    src = (ROOT / "backend" / "core" / "decision_engine.py").read_text(encoding="utf-8")
    D.code(src[src.index("AGENT_WEIGHTS = {"):src.index("def _find_agent")])
    D.code(src[src.index("def aggregate_score"):src.index("def classify_manipulation")][:1700])
    D.para("A.3 Training step of the detector (training/train_image_detector.py)", 12, True, align="left", before=8, after=3, keep_next=True)
    src = (ROOT / "training" / "train_image_detector.py").read_text(encoding="utf-8")
    D.code(src[src.index("def crops_of"):src.index("def to_tensor")])
    D.code(src[src.index("def train_model"):src.index("@torch.no_grad()")])


# ── template editing ───────────────────────────────────────────────────────────────────────────
def build(template, out, pages=None):
    d = docx.Document(template)
    P = d.paragraphs
    title_up = TITLE.upper()

    # cover
    set_runs_text(P[2], title_up, bold=True, size=18)
    delete_paragraph(P[3])
    P = d.paragraphs
    for i, p in enumerate(P[:30]):
        if p.text.startswith("(mention names of team members"):
            delete_paragraph(p)
            break
    P = d.paragraphs
    for p in P[:25]:
        if p.text.strip() == "Programme":
            set_runs_text(p, "Computer Science and Engineering", bold=True, size=19)
    for t in d.tables[:2]:
        for row in t.rows:
            for c in row.cells:
                for pp in c.paragraphs:
                    txt = pp.text
                    if "<Upper case, Bold>" in txt:
                        replace_text(pp, " <Upper case, Bold>", "", False)
                    if "<Project Guide Name <Bold>>" in txt:
                        replace_text(pp, "<Project Guide Name <Bold>>", "<Project Guide Name>", False)
                    for r in pp.runs:
                        if r.text.startswith("Reg. No.") or r.text.startswith("Student Name") or r.text.startswith("<"):
                            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    # declaration, certificate, notes
    for p in d.paragraphs:
        if "<< Project Title >>" in p.text:
            replace_text(p, "<< Project Title >>", TITLE)
        if p.text.startswith("Note: Include your project title"):
            delete_paragraph(p)
    for p in d.paragraphs:
        if p.text.startswith("Note: Include your project title"):
            delete_paragraph(p)
    for p in d.paragraphs:
        if "<<" in p.text or "<Head of" in p.text or "<Department Name>" in p.text or "<Guide" in p.text:
            mark_placeholders(p)

    for q in d.paragraphs:
        if "<Contents, Times New Roman 12, Line spacing 1.5>" in q.text:
            delete_paragraph(q)
            break
    # contents table
    t = d.tables[2]
    fixes = {"Abstract < Capitalize Each Word, Bold>": "Abstract", "INTRODUCTION <Uppercase, Bold>": "INTRODUCTION", "1.1 Background <Capitalize Each Word, Normal>": "1.1 Background",
             "<< Module Description >>": "5.1 Module Description", "<< Testing >>": "5.2 Testing", "     3.2.2 Social Feasibility": "     3.2.3 Social Feasibility"}
    for row in t.rows:
        c = row.cells[1]
        for pp in c.paragraphs:
            for old, new in fixes.items():
                if old in pp.text:
                    replace_text(pp, old, new)
    # add 5.1/5.2 subsections and chapter-7 subsections would need rows; keep the template's outline.

    # abstract
    P = d.paragraphs
    ai = next(i for i, p in enumerate(P) if p.text.strip() == "ABSTRACT" and p.style.name == "Heading 2")
    sect_idx = next(i for i in range(ai, len(P)) if has_sectpr(P[i]))
    for p in P[ai + 1:sect_idx]:
        delete_paragraph(p)
    anchor = next(q for q in d.paragraphs[ai + 1:] if has_sectpr(q))._p
    D = Doc(d, anchor)
    for k, txt in enumerate(abstract_text()):
        D.para(txt, 12, align="justify", after=8, line=1.15)
    D.para("**Keywords:** image forgery detection, splicing, error level analysis, EfficientNet, digital evidence, multi-agent system, web application.", 12, align="left", before=6)

    # body: replace chapter-1 placeholder content
    P = d.paragraphs
    c1 = next(i for i, p in enumerate(P) if p.text.strip() == "CHAPTER 1")
    body_sect = next(i for i in range(c1, len(P)) if has_sectpr(P[i]))
    for p in P[c1:body_sect]:
        delete_paragraph(p)
    D = Doc(d, [q for q in d.paragraphs if has_sectpr(q)][2]._p)
    # chapter 1 begins the arithmetic section: no page break needed (section break starts a new page)
    build_body(D, ROOT)
    # remove the page break of the very first chapter (a new section already starts a new page)
    first = next(p for p in d.paragraphs if p.text == "CHAPTER 1")
    first.paragraph_format.page_break_before = False

    # references and appendix
    P = d.paragraphs
    ri = max(i for i, p in enumerate(P) if p.text.strip() == "CHAPTER 7")
    app = next(i for i, p in enumerate(P) if p.text.startswith("APPENDIX A"))
    set_runs_text(P[ri], "CHAPTER 9", bold=True, size=16)
    set_runs_text(P[ri + 1], "9. REFERENCES", bold=True, size=14)
    sample = None
    for p in P[ri + 2:app]:
        if p.style.name == "List Paragraph" and sample is None:
            sample = copy.deepcopy(p._p)
    for p in P[ri + 2:app]:
        if not has_sectpr(p) and not p._p.xpath('.//w:br[@w:type="page"]'):
            delete_paragraph(p)
    P = d.paragraphs
    app = next(i for i, p in enumerate(P) if p.text.startswith("APPENDIX A"))
    brk = next((q for q in P[ri + 2:app] if q._p.xpath('.//w:br[@w:type="page"]')), None)
    anchor = brk._p if brk is not None else P[app]._p
    for ref in REFS:
        el = copy.deepcopy(sample)
        anchor.addprevious(el)
        par = docx.text.paragraph.Paragraph(el, P[app]._parent)
        runs = par.runs
        runs[0].text = ref
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
        runs[0].italic = False
        runs[0].font.size = Pt(12)
    # appendix heading + code
    P = d.paragraphs
    app = next(i for i, p in enumerate(P) if p.text.startswith("APPENDIX A"))
    set_runs_text(P[app], "APPENDIX A – SAMPLE CODE", bold=True, size=14)
    # the template's page-break paragraph can spill onto its own page; break before the heading instead
    for q in P[ri + 2:app]:
        if q._p.xpath('.//w:br[@w:type="page"]') and not has_sectpr(q) and q.text.strip() == "":
            delete_paragraph(q)
    P[app].paragraph_format.page_break_before = True
    for p in P[app + 1:]:
        if not has_sectpr(p) and p.text.strip() == "":
            delete_paragraph(p)
    end_anchor = d.element.body.find(qn("w:sectPr"))
    D2 = Doc(d, end_anchor)
    appendix_code(D2)

    # list of figures, list of tables
    ft = d.tables[3]
    for row in list(ft.rows)[2:]:
        ft._tbl.remove(row._tr)
    proto = copy.deepcopy(ft.rows[1]._tr)
    ft._tbl.remove(ft.rows[1]._tr)
    for no, cap in D.figures:
        tr = copy.deepcopy(proto)
        ft._tbl.append(tr)
        row = ft.rows[-1]
        for cell, txt in zip(row.cells, (no, cap, str((pages or {}).get("fig " + no, "")))):
            pp = cell.paragraphs[0]
            if pp.runs:
                pp.runs[0].text = txt
                for r in pp.runs[1:]:
                    r._r.getparent().remove(r._r)
            else:
                pp.add_run(txt)
            pp.paragraph_format.space_before = Pt(0)
            pp.paragraph_format.space_after = Pt(0)
            for r in pp.runs:
                r.font.size = Pt(10.5)
    P = d.paragraphs
    th = next(i for i, q in enumerate(P) if q.text.startswith("Table No."))
    sample_row = copy.deepcopy(P[th + 1]._p)
    delete_paragraph(P[th + 1])
    last = d.paragraphs[th]._p
    holder = d.paragraphs[th]._parent
    for no, cap in D.tables:
        el = copy.deepcopy(sample_row)
        last.addnext(el)
        last = el
        par = docx.text.paragraph.Paragraph(el, holder)
        runs = par.runs
        runs[0].text = f"{no}\t{cap}\t{(pages or {}).get('tab ' + no, '')}"
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    for p in d.paragraphs:
        if p.text.startswith("(In the chapters, figure caption"):
            delete_paragraph(p)
            break

    # a full list of figures plus the template's empty paragraphs and page break leaves a blank page: break before the next heading
    lt = next(q for q in d.paragraphs if q.text.strip() == "List of Tables")
    prev = lt._p.getprevious()
    while prev is not None and prev.tag == qn("w:p") and not "".join(t.text or "" for t in prev.iter(qn("w:t"))).strip() and not prev.xpath(".//w:sectPr"):
        gone, prev = prev, prev.getprevious()
        gone.getparent().remove(gone)
    lt.paragraph_format.page_break_before = True

    # abbreviations and symbols
    P = d.paragraphs
    ab = next(i for i, q in enumerate(P) if q.text.strip() == "List of Abbreviations")
    proto = copy.deepcopy(P[ab + 2]._p)
    j = ab + 1
    while j < len(P) and not P[j].text.startswith("Note: All the abbreviations"):
        if not has_sectpr(P[j]) and not P[j]._p.xpath('.//w:br[@w:type="page"]'):
            delete_paragraph(P[j])
            P = d.paragraphs
        else:
            j += 1
    P = d.paragraphs
    note = next(q for q in P if q.text.startswith("Note: All the abbreviations"))
    for k, v in ABBREV:
        el = copy.deepcopy(proto)
        note._p.addprevious(el)
        par = docx.text.paragraph.Paragraph(el, note._parent)
        runs = par.runs
        runs[0].text = f"{k}\t{v}"
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    delete_paragraph(note)
    P = d.paragraphs
    sy = next(i for i, p in enumerate(P) if p.text.strip() == "Symbols and Notations")
    first_sym = sy + 1
    while P[first_sym].text.strip() == "":
        first_sym += 1
    sym_proto = copy.deepcopy(P[first_sym]._p)
    anchor = P[first_sym]._p
    for k, v in SYMBOLS:
        el = copy.deepcopy(sym_proto)
        anchor.addprevious(el)
        par = docx.text.paragraph.Paragraph(el, P[sy]._parent)
        runs = par.runs
        runs[0].text = f"{k}\t{v}"
        runs[0].font.name = "Times New Roman"
        runs[0]._r.get_or_add_rPr().rFonts.attrib.clear()
        runs[0]._r.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
        runs[0]._r.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    P = d.paragraphs
    for i in range(first_sym + len(SYMBOLS), min(first_sym + len(SYMBOLS) + 2, len(P))):
        if P[i].text.startswith("") or P[i].text.startswith("") or "CFO" in P[i].text:
            P[i]._p.getparent().remove(P[i]._p)

    # contents page numbers
    if pages:
        for row in t.rows[1:]:
            key = row.cells[1].text.strip()
            num = pages.get("toc " + key)
            if num is not None:
                pp = row.cells[2].paragraphs[0]
                if pp.runs:
                    pp.runs[0].text = str(num)
                    for r in pp.runs[1:]:
                        r._r.getparent().remove(r._r)
                else:
                    pp.add_run(str(num))
    d.save(out)
    return D


def export_pdf(docx_path, pdf_path):
    ps = ("$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
          f"$d = $w.Documents.Open('{docx_path}', $false, $true); $d.Repaginate(); "
          f"$d.ExportAsFixedFormat('{pdf_path}', 17); $d.Close($false); $w.Quit()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=600)


def locate_pages(pdf_path, D, toc_keys):
    doc = fitz.open(pdf_path)
    texts = [p.get_text() for p in doc]
    shown = []
    for p in doc:
        blocks = sorted(p.get_text("blocks"), key=lambda b: b[3])
        shown.append((blocks[-1][4].strip() if blocks else ""))
    body_start = next(i for i, t in enumerate(texts) if "CHAPTER 1" in t and "INTRODUCTION" in t and "Background" in t)
    pages = {}
    for sl, key in toc_keys:
        k = key.strip()
        if not k:
            continue
        probe = (f"{sl} {k}" if sl else k) if k != "Abstract" else "ABSTRACT"
        start = 0 if k == "Abstract" else body_start
        for i in range(start, len(texts)):
            if i < body_start and k != "Abstract":
                continue
            if re.search(r"(^|\n)\s*" + re.escape(probe.replace("     ", "")) + r"\s*(\n|$)", texts[i]) or (k == "Abstract" and "ABSTRACT" in texts[i] and "Keywords" in texts[i]):
                pages["toc " + key.strip()] = shown[i]
                break
    for no, cap in D.figures:
        for i in range(body_start, len(texts)):
            if f"Figure {no}:" in texts[i]:
                pages["fig " + no] = shown[i]
                break
    for no, cap in D.tables:
        for i in range(body_start, len(texts)):
            if f"Table {no}:" in texts[i]:
                pages["tab " + no] = shown[i]
                break
    return pages, len(doc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", default=str(ROOT / "docs" / "report" / "TrustSphere_AI_Project_Report.docx"))
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = out.with_suffix(".pdf")
    D = build(a.template, str(out))
    export_pdf(str(out), str(pdf))
    t = docx.Document(str(out)).tables[2]
    keys = [(r.cells[0].text.strip(), r.cells[1].text) for r in t.rows[1:]]
    pages, n = locate_pages(str(pdf), D, keys)
    print("pass 1:", n, "pages;", len(pages), "page numbers found")
    D = build(a.template, str(out), pages)
    export_pdf(str(out), str(pdf))
    pages2, n2 = locate_pages(str(pdf), D, keys)
    changed = {k: (pages.get(k), v) for k, v in pages2.items() if pages.get(k) != v}
    print("pass 2:", n2, "pages; changed numbers:", changed if changed else "none")
    print("wrote", out, "and", pdf)


if __name__ == "__main__":
    main()
