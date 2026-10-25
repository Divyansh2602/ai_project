"""Evaluation of TrustSphere (image-only): cross-validated detector results, pipeline results on held-out images, localisation, comparison.

Inputs written by training/ (docs/evaluation/training/*.json, *.csv):
    cv_casia_v2_random.json / oof_casia_v2_random.csv      5-fold cross-validation, random split
    cv_casia_v2_group.json  / oof_casia_v2_group.csv       5-fold cross-validation, tampered image kept with its source image
    cv_columbia_*.json / oof_columbia_*.csv                Columbia cross-validation (several inputs)
    holdout_casia_v2_group.json                            80/20 source-disjoint split: weights trained on 80 %, the 20 % file list
    localizer_results.json                                 pixel-level localisation (train CASIA v2.0, test Columbia)

The pipeline evaluation runs the REAL agents and decision engine (the same path as an upload) on the held-out 20 % with the held-out weights, so no
test image was ever seen by the detector. Writes docs/evaluation/: metrics.json, predictions.csv, figures, sample outputs and EVALUATION.md.

    python scripts/evaluate_images.py
"""
import json
import os
import shutil
import sys
import tempfile
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TR = ROOT / "docs" / "evaluation" / "training"
OUT = ROOT / "docs" / "evaluation"
SCRATCH = Path(tempfile.mkdtemp(prefix="ts_eval_"))
os.environ.setdefault("HEATMAP_DIR", str(SCRATCH / "heatmaps"))
os.environ["POLYGON_PRIVATE_KEY"] = ""

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PIL import Image, ImageFile  # noqa: E402
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve  # noqa: E402

ImageFile.LOAD_TRUNCATED_IMAGES = True
CLASSES = ["Authentic", "Fake", "Inconclusive"]
BLUE, RED, GREEN, GREY = "#1560bd", "#c0392b", "#1a8f4c", "#5b6b80"


# ── helpers ────────────────────────────────────────────────────────────────────────────
def pc(v, d=2):
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def eer(y, s):
    fpr, tpr, _ = roc_curve(y, s)
    i = int(np.nanargmin(np.abs((1 - tpr) - fpr)))
    return float((fpr[i] + 1 - tpr[i]) / 2)


def binary_metrics(y, p, thr=0.5):
    y = np.asarray(y)
    pred = (np.asarray(p) >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    prec, rec = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return {"n": int(len(y)), "accuracy": float((pred == y).mean()), "precision": float(prec), "recall": float(rec),
            "specificity": float(tn / max(1, tn + fp)), "f1": float(2 * prec * rec / max(1e-9, prec + rec)),
            "balanced_accuracy": float((rec + tn / max(1, tn + fp)) / 2), "roc_auc": float(roc_auc_score(y, p)), "eer": eer(y, p),
            "confusion": [[int(tn), int(fp)], [int(fn), int(tp)]]}


def fig_binary(title, y, p, path, thr=0.5, pred=None):
    """Confusion matrix at thr (or from the given hard predictions), ROC and score histogram of p."""
    y, p = np.asarray(y), np.asarray(p)
    m = binary_metrics(y, p if pred is None else np.asarray(pred, float), thr)
    m["roc_auc"], m["eer"] = float(roc_auc_score(y, p)), eer(y, p)
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
    cm = np.array(m["confusion"])
    ax[0].imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax[0].text(j, i, cm[i, j], ha="center", va="center", fontsize=17, fontweight="bold", color="white" if cm[i, j] > cm.max() / 2 else "#0f1b2d")
    ax[0].set_xticks([0, 1]); ax[0].set_xticklabels(["Authentic", "Manipulated"]); ax[0].set_yticks([0, 1]); ax[0].set_yticklabels(["Authentic", "Manipulated"])
    ax[0].set_xlabel("Predicted"); ax[0].set_ylabel("True"); ax[0].set_title(f"Confusion matrix (accuracy {m['accuracy'] * 100:.2f}%)")
    fpr, tpr, _ = roc_curve(y, p)
    ax[1].plot(fpr, tpr, color=BLUE, lw=2.3, label=f"AUC = {m['roc_auc']:.4f}")
    ax[1].plot([0, 1], [0, 1], "--", color="#9aa7b8"); ax[1].set_xlabel("False positive rate"); ax[1].set_ylabel("True positive rate")
    ax[1].set_title("ROC curve"); ax[1].legend(loc="lower right"); ax[1].grid(alpha=.25)
    bins = np.linspace(0, 1, 26)
    ax[2].hist(p[y == 0], bins=bins, alpha=.8, color=GREEN, label="authentic")
    ax[2].hist(p[y == 1], bins=bins, alpha=.8, color=RED, label="manipulated")
    (ax[2].axvline(thr, color=GREY, ls="--") if pred is None else None); ax[2].set_xlabel("predicted probability of manipulation"); ax[2].set_ylabel("images")
    ax[2].set_title("Score distribution"); ax[2].legend()
    fig.suptitle(title, fontweight="bold")
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)
    return m


def cv_block(name, json_name, csv_name, rep, figs, score_col="p_fake"):
    jp, cp = TR / json_name, TR / csv_name
    if not (jp.exists() and cp.exists()):
        return None
    j = json.loads(jp.read_text(encoding="utf-8"))
    df = pd.read_csv(cp)
    m = fig_binary(name, df["label"], df[score_col], OUT / f"cv_{Path(json_name).stem[3:]}.png")
    rep[name] = {"mean_fold_accuracy": j["mean_fold_accuracy"], "std_fold_accuracy": j["std_fold_accuracy"],
                 "folds": [round(f["accuracy"], 4) for f in j["folds"]], "pooled": m, "input": j.get("input"), "epochs": j.get("epochs")}
    figs.append((name, f"cv_{Path(json_name).stem[3:]}.png"))
    return rep[name]


# ── pipeline evaluation on the held-out images ──────────────────────────────────────────────
def pipeline_eval(rep, figs):
    hp = TR / "holdout_casia_v2_group.json"
    if not hp.exists():
        return None
    h = json.loads(hp.read_text(encoding="utf-8"))
    mf = SCRATCH / "manifest.json"
    wdir = ROOT / "backend" / "models" / "trained"
    mf.write_text(json.dumps({"detectors": [{"file": str((wdir / h["weights"]).resolve()), "name": "hold-out detector (80% of CASIA v2.0)"}]}), encoding="utf-8")
    os.environ["TRUSTSPHERE_DETECTOR_MANIFEST"] = str(mf)
    import core.trained_detector as td
    td._DIR = Path("/")     # absolute weight path in the manifest
    from agents import image_agent, metadata_agent, security_agent
    from core.decision_engine import AUTHENTIC_THRESHOLD, FAKE_THRESHOLD, decide
    assert td.available(), td._state.get("error")
    rows, store = [], {}
    t0 = time.time()
    for i, (f, y) in enumerate(zip(h["test_files"], h["test_labels"]), 1):
        res = [metadata_agent.run(f), image_agent.run(f), security_agent.run(f)]
        d = decide(res, "image")
        name = Path(f).name
        sub = "Authentic" if y == 0 else ("Tampered: splicing (Tp_D)" if name.startswith("Tp_D") else "Tampered: copy-move (Tp_S)")
        rows.append({"file": name, "path": f, "subset": sub, "label": y, "verdict": d["verdict"], "score": float(d["overall_score"]),
                     "p_manipulated": 1 - [a for a in res if a["agent"] == "image_forensics"][0]["confidence"], "manipulation_type": d.get("manipulation_type")})
        store[f] = (res, d)
        if i % 100 == 0 or i == len(h["test_files"]):
            print(f"  pipeline {i}/{len(h['test_files'])} ({time.time() - t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    y, pred, score = df["label"].to_numpy(), df["verdict"].to_numpy(), df["score"].to_numpy()
    decided = pred != "Inconclusive"
    pb = np.where(pred == "Fake", 1, np.where(pred == "Authentic", 0, -1))
    cm3 = [[int(((y == t) & (pred == c)).sum()) for c in CLASSES] for t in (0, 1)]
    forced = binary_metrics(y, 1 - score)
    m = {"n": int(len(df)), "n_authentic": int((y == 0).sum()), "n_fake": int((y == 1).sum()), "coverage_decided": float(decided.mean()),
         "accuracy_on_decided": float((pb[decided] == y[decided]).mean()) if decided.any() else None, "accuracy_strict": float((pb == y).mean()),
         "forced_two_way": forced, "confusion_engine": cm3, "thresholds": [AUTHENTIC_THRESHOLD, FAKE_THRESHOLD],
         "false_positive_rate": float(((pred == "Fake") & (y == 0)).sum() / max(1, (y == 0).sum())),
         "false_negative_rate": float(((pred == "Authentic") & (y == 1)).sum() / max(1, (y == 1).sum())),
         "detector_alone": binary_metrics(y, df["p_manipulated"]), "by_subset": {}}
    for s, g in df.groupby("subset"):
        want = "Authentic" if g["label"].iloc[0] == 0 else "Fake"
        m["by_subset"][s] = {"n": int(len(g)), "correct": float((g.verdict == want).mean()), "inconclusive": float((g.verdict == "Inconclusive").mean()),
                             "wrong": float(((g.verdict != want) & (g.verdict != "Inconclusive")).mean())}
    # engine-verdict confusion figure
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw={"width_ratios": [1.2, 1]})
    c = np.array(cm3)
    ax[0].imshow(c, cmap="Blues")
    for i in range(2):
        for j in range(3):
            ax[0].text(j, i, c[i, j], ha="center", va="center", fontsize=17, fontweight="bold", color="white" if c[i, j] > c.max() / 2 else "#0f1b2d")
    ax[0].set_xticks(range(3)); ax[0].set_xticklabels(CLASSES); ax[0].set_yticks([0, 1]); ax[0].set_yticklabels(["Authentic", "Manipulated"])
    ax[0].set_xlabel("Decision-engine verdict"); ax[0].set_ylabel("True"); ax[0].set_title("Pipeline verdicts on the held-out images")
    labels = list(m["by_subset"])
    x = np.arange(len(labels))
    cc = [m["by_subset"][s]["correct"] for s in labels]; ii = [m["by_subset"][s]["inconclusive"] for s in labels]; ww = [m["by_subset"][s]["wrong"] for s in labels]
    ax[1].bar(x, cc, color=GREEN, label="correct"); ax[1].bar(x, ii, bottom=cc, color="#d9a21b", label="Inconclusive")
    ax[1].bar(x, ww, bottom=np.array(cc) + np.array(ii), color=RED, label="wrong")
    ax[1].set_xticks(x); ax[1].set_xticklabels([s.replace(": ", ":\n") for s in labels], fontsize=9); ax[1].set_ylim(0, 1.05); ax[1].legend(loc="lower center", ncol=3, fontsize=8)
    ax[1].set_title("Outcome per subset")
    fig.tight_layout(); fig.savefig(OUT / "pipeline_holdout.png", dpi=140); plt.close(fig)
    fig_binary("Hold-out detector probability (agent output, before the decision engine)", y, df["p_manipulated"], OUT / "pipeline_holdout_detector.png")
    # sample outputs: most confident correct and most confident wrong per class
    ch = []
    for s, g in df.groupby("subset"):
        want = "Authentic" if g["label"].iloc[0] == 0 else "Fake"
        ok = g[g.verdict == want]
        if len(ok):
            ch.append((s, "correct", ok.sort_values("score", ascending=(want == "Fake")).iloc[0]))
        bad = g[(g.verdict != want)]
        if len(bad):
            ch.append((s, "missed or Inconclusive", bad.sort_values("score", ascending=(want != "Fake")).iloc[0]))
    fig, ax = plt.subplots(len(ch), 3, figsize=(11, 3.2 * len(ch)))
    ax = np.atleast_2d(ax)
    (OUT / "samples").mkdir(exist_ok=True)
    for k, (s, kind, r) in enumerate(ch):
        res, d = store[r["path"]]
        ia = [a for a in res if a["agent"] == "image_forensics"][0]
        ax[k, 0].imshow(Image.open(r["path"]).convert("RGB")); ax[k, 0].set_title(f"{s}\ntruth: {'Manipulated' if r['label'] else 'Authentic'}", fontsize=9)
        for j, (key, t) in enumerate(((ia.get("heatmap_path"), "Error-level analysis"), (ia.get("gradcam_path"), "Model attention (Grad-CAM)")), start=1):
            if key and Path(key).exists():
                ax[k, j].imshow(Image.open(key))
            ax[k, j].set_title(t if j == 2 else f"{t}\nverdict {r['verdict']} ({r['score']:.2f}), {kind}", fontsize=9)
        for j in range(3):
            ax[k, j].axis("off")
        (OUT / "samples" / f"{Path(r['file']).stem[:60]}_{kind.split()[0]}.json").write_text(json.dumps(
            {"file": r["file"], "subset": s, "truth": "Manipulated" if r["label"] else "Authentic", "outcome": kind, "decision": d,
             "agents": [{a: b for a, b in ag.items() if a != "heatmap_path"} for ag in res]}, indent=1, default=str), encoding="utf-8")
    fig.tight_layout(); fig.savefig(OUT / "pipeline_samples.png", dpi=110); plt.close(fig)
    df.drop(columns=["path"]).to_csv(OUT / "predictions.csv", index=False)
    figs.append(("pipeline", "pipeline_holdout.png"))
    rep["pipeline_holdout"] = m
    return m


# ── report ───────────────────────────────────────────────────────────────────────────────────
def write_md(rep):
    L = ["# TrustSphere AI: evaluation (image-only)", "",
         "All numbers on this page are produced by code in this repository (`training/`, `scripts/evaluate_images.py`) from out-of-fold or held-out predictions; "
         "no image is scored by a model that trained on it. Datasets: CASIA v2.0 (1,536 authentic + 1,283 tampered) and Columbia (183 authentic + 180 spliced), "
         "both from the Hugging Face compilation `ductai199x/image-manipulation-dataset-compilation`. Class 1 = manipulated.", ""]
    L += ["## 1. Detector accuracy by cross-validation", "",
          "| experiment | input | accuracy (mean of 5 folds +- std) | pooled accuracy | ROC AUC | EER | precision | recall | F1 |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in rep.items():
        if isinstance(v, dict) and "mean_fold_accuracy" in v:
            p = v["pooled"]
            L.append(f"| {k} | {v.get('input')} | {v['mean_fold_accuracy'] * 100:.2f} +- {v['std_fold_accuracy'] * 100:.2f} | {pc(p['accuracy'])} | {p['roc_auc']:.4f} | {pc(p['eer'])} | {pc(p['precision'])} | {pc(p['recall'])} | {pc(p['f1'])} |")
    L += ["", "Fold accuracies: " + "; ".join(f"{k}: {', '.join(f'{a * 100:.1f}' for a in v['folds'])}" for k, v in rep.items() if isinstance(v, dict) and "folds" in v) + ".", ""]
    for k, fn in rep.get("_figs", []):
        L += [f"### {k}", "", f"![{k}]({fn})", ""]
    ph = rep.get("pipeline_holdout")
    if ph:
        c = ph["confusion_engine"]
        L += ["## 2. The full pipeline on held-out images", "",
              f"{ph['n']} CASIA v2.0 images ({ph['n_authentic']} authentic, {ph['n_fake']} tampered) that the detector never saw (80/20 split that keeps every tampered image with its source image). "
              "The real agents (metadata, image forensics with the trained detector, provenance) and the decision engine run on each file.", "",
              "| | Authentic | Fake | Inconclusive |", "|---|---|---|---|",
              f"| **True authentic** | {c[0][0]} | {c[0][1]} | {c[0][2]} |", f"| **True tampered** | {c[1][0]} | {c[1][1]} | {c[1][2]} |", "",
              f"* Verdict bands: Authentic at or above {ph['thresholds'][0]}, Fake at or below {ph['thresholds'][1]}, otherwise Inconclusive.",
              f"* Decided by the engine: {pc(ph['coverage_decided'])}; accuracy on decided files {pc(ph['accuracy_on_decided'])}; strict accuracy (Inconclusive counted wrong) {pc(ph['accuracy_strict'])}.",
              f"* Forced two-way call from the engine score (below 0.5 = Fake): accuracy {pc(ph['forced_two_way']['accuracy'])}, ROC AUC {ph['forced_two_way']['roc_auc']:.4f}, EER {pc(ph['forced_two_way']['eer'])}.",
              f"* Detector probability alone: accuracy {pc(ph['detector_alone']['accuracy'])}, ROC AUC {ph['detector_alone']['roc_auc']:.4f}.",
              f"* Authentic images called Fake: {pc(ph['false_positive_rate'])}; tampered images called Authentic: {pc(ph['false_negative_rate'])}.", "",
              "![pipeline hold-out](pipeline_holdout.png)", "", "![detector hold-out](pipeline_holdout_detector.png)", "",
              "| subset | n | correct verdict | Inconclusive | wrong verdict |", "|---|---|---|---|---|"]
        for s, v in ph["by_subset"].items():
            L.append(f"| {s} | {v['n']} | {pc(v['correct'])} | {pc(v['inconclusive'])} | {pc(v['wrong'])} |")
        L += ["", "### Sample outputs", "", "![samples](pipeline_samples.png)", "", "Raw agent and decision output for these samples is in [samples/](samples/).", ""]
    lz = rep.get("localizer")
    if lz:
        L += ["## 3. Pixel-level localisation (GIFT protocol)", "",
              "A U-Net-style network (EfficientNet-B0 encoder on RGB plus multi-quality ELA) trained on CASIA v2.0 only and tested on Columbia, which it never saw "
              f"(threshold {lz['threshold_from_casia_validation']:.2f} chosen on CASIA validation).", "",
              "| set | pooled pixel F1 | mean per-image pixel F1 | pixel AUC | image AUC from the map |", "|---|---|---|---|---|"]
        for k in ("casia_validation", "columbia"):
            v = lz[k]
            L.append(f"| {v['set']} | {v['pixel_f1_pooled']:.4f} | {v['pixel_f1_mean_per_image']:.4f} | {v['pixel_auc']:.4f} | {v.get('image_auc_from_map', float('nan')):.4f} |")
        L += ["", "GIFT (Chen et al. 2026) reports pixel F1 0.6497 (0.6558 with edge supervision) on Columbia under the same train-on-CASIA protocol. "
              "**Our localiser is clearly below that on Columbia**: it localises well on CASIA validation images but does not transfer to Columbia's uncompressed photographs.", ""]
    L += ["## 4. Comparison with the five base papers", "",
          "Each row compares like with like (same dataset, same kind of metric). Protocols still differ (their splits, subsets and training data), so treat this as context, not a leaderboard.", "",
          "| base paper | dataset | metric | reported | TrustSphere | result |", "|---|---|---|---|---|---|"]
    cr = rep.get("CASIA v2.0, random 5-fold")
    cg = rep.get("CASIA v2.0, source-disjoint 5-fold")
    if cr and cg:
        a, b = cr["pooled"], cg["pooled"]
        L += [f"| SD31 Ravula et al. 2025 (GAN-ViT-CMFD) | CASIA v2.0 | accuracy | 94.4% | {pc(a['accuracy'])} random / {pc(b['accuracy'])} source-disjoint | above |",
              f"| SD35 Rehman et al. 2025 (CNN + SVM) | CASIA v2.0 | accuracy | 98.91% best figure (batch 128, mean over folds 93.39%); 93.57% (batch 200, mean 90.25%) | {pc(a['accuracy'])} / {pc(b['accuracy'])} | above both fold means and the 93.57% figure; below the 98.91% best figure |",
              f"| SD52 Deb et al. 2026 (Satyachitra) | CASIA v2.0 | precision / recall / F1 | 87.31 / 90.15 / 88.33 | {pc(a['precision'])} / {pc(a['recall'])} / {pc(a['f1'])} | above |",
              f"| SD25 Ranjan et al. 2026 (LOOP + ResNet-50 + SVM) | Columbia, CASIA v2.0, Dresden pooled | accuracy | 95.20% | CASIA alone {pc(a['accuracy'])} (Dresden not used here) | level on CASIA; see the pooled row |"]
    colp = rep.get("Columbia, patch-based, SRM input")
    colg = rep.get("Columbia, patch-based, SRM input, scene-disjoint")
    if colp:
        g = f" / {pc(colg['pooled']['accuracy'])} scene-disjoint" if colg else ""
        top = min(colp["pooled"]["accuracy"], colg["pooled"]["accuracy"]) if colg else colp["pooled"]["accuracy"]
        L.append(f"| SD25 table of earlier Columbia methods | Columbia | accuracy | 91 to 93.4% | {pc(colp['pooled']['accuracy'])} random{g} (patch-based) | {'above' if top > 0.934 else 'above only under the random split' if colp['pooled']['accuracy'] > 0.934 else 'below'} |")
    pr = rep.get("pooled_casia_columbia_random")
    if pr:
        pg = rep.get("pooled_casia_columbia_group")
        L.append(f"| SD25 Ranjan et al. 2026 (pooled average, Dresden included there) | CASIA v2.0 + Columbia pooled | accuracy | 95.20% | {pc(pr['accuracy'])} random" + (f" / {pc(pg['accuracy'])} source- and scene-disjoint" if pg else "") + " | see text |")
    if lz:
        L.append(f"| GIFT Chen et al. 2026 | Columbia (trained on CASIA v2.0) | pixel F1 | 0.6497 / 0.6558 | {lz['columbia']['pixel_f1_pooled']:.4f} | below |")
    L += ["", "### Other CASIA v2.0 results found outside the reference folder (not verified against the papers)", "",
          "| source | reported on CASIA v2.0 |", "|---|---|",
          "| Depth-wise CNN (MobileNet-based), IIETA | 99.37% accuracy |", "| ELA + CNN (PMC study) | 94.14% and 96.21% |", "| ELA + HOG with SVM (2025) | 95.50% |",
          "| EfficientNet-B0 image fake-news study | 96.11% |", "| ELA + MobileNetV2 (2025) | 93.1% |", "| CNN on 9,319 CASIA v2.0 images | 92.5% |", "",
          "These include papers above our accuracy. They are listed here for completeness.", ""]
    (OUT / "EVALUATION.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rep, figs = {}, []
    cv_block("CASIA v2.0, random 5-fold", "cv_casia_v2_random.json", "oof_casia_v2_random.csv", rep, figs)
    cv_block("CASIA v2.0, source-disjoint 5-fold", "cv_casia_v2_group.json", "oof_casia_v2_group.csv", rep, figs)
    cv_block("Columbia, whole-image, ELA input", "cv_columbia_random.json", "oof_columbia_random.csv", rep, figs)
    cv_block("Columbia, whole-image, SRM input", "cv_columbia_random_srm.json", "oof_columbia_random_srm.csv", rep, figs)
    for tag, name in (("random", "Columbia, patch-based, SRM input"), ("group", "Columbia, patch-based, SRM input, scene-disjoint")):
        pj, pc_ = TR / f"cv_columbia_{tag}_patch_srm.json", TR / f"oof_columbia_{tag}_patch_srm.csv"
        if not (pj.exists() and pc_.exists()):
            continue
        j = json.loads(pj.read_text(encoding="utf-8"))
        df = pd.read_csv(pc_)
        y, sc = df["label"].to_numpy(), df["score"].to_numpy()
        png = f"cv_columbia_{tag}_patch_srm.png"
        m = fig_binary(f"{name} (threshold from the other folds)", y, sc, OUT / png, pred=df["pred"].to_numpy())
        rep[name] = {"mean_fold_accuracy": j["mean_fold_accuracy"], "std_fold_accuracy": j["std_fold_accuracy"],
                     "folds": [round(f["accuracy"], 4) for f in j["folds"]], "pooled": m, "input": "srm (patches)", "epochs": j.get("steps")}
        figs.append((name, png))
    lz = TR / "localizer_results.json"
    if lz.exists():
        rep["localizer"] = json.loads(lz.read_text(encoding="utf-8"))
    pipeline_eval(rep, figs)
    try:
        c = pd.read_csv(TR / "oof_casia_v2_random.csv")
        k = pd.read_csv(TR / "oof_columbia_random_patch_srm.csv")
        n1, a1 = len(c), float(((c["p_fake"] >= 0.5).astype(int) == c["label"]).mean())
        n2, a2 = len(k), float((k["pred"] == k["label"]).mean())
        rep["pooled_casia_columbia_random"] = {"n": n1 + n2, "accuracy": (n1 * a1 + n2 * a2) / (n1 + n2)}
        kg = TR / "oof_columbia_group_patch_srm.csv"
        if kg.exists():
            k2 = pd.read_csv(kg)
            cg = pd.read_csv(TR / "oof_casia_v2_group.csv")
            m1, b1 = len(cg), float(((cg["p_fake"] >= 0.5).astype(int) == cg["label"]).mean())
            m2, b2 = len(k2), float((k2["pred"] == k2["label"]).mean())
            rep["pooled_casia_columbia_group"] = {"n": m1 + m2, "accuracy": (m1 * b1 + m2 * b2) / (m1 + m2)}
    except Exception as exc:
        print("pooled accuracy skipped:", exc)
    rep["_figs"] = figs
    (OUT / "metrics.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    write_md(rep)
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print("wrote", OUT / "EVALUATION.md")


if __name__ == "__main__":
    main()
