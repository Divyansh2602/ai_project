"""Splicing localisation (pixel-level) following the GIFT protocol: train on CASIA v2.0, test on Columbia.

GIFT (Chen et al., J. Vis. Commun. Image Represent. 118 (2026) 104797) trains on CASIA v2.0 and tests on other datasets, reporting pixel F1
(Columbia 0.6497, edge-enhanced 0.6558) and AUC. This script trains a small U-Net-style network (EfficientNet-B0 encoder on RGB + multi-quality ELA)
on CASIA v2.0 and evaluates it on Columbia without ever using Columbia for training, threshold selection or early stopping.

    python training/train_localizer.py --epochs 30
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import timm
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import INDEXES, ela_multi, find  # noqa: E402

REPO = HERE.parent
OUT = REPO / "docs" / "evaluation" / "training"
WEIGHTS = REPO / "backend" / "models" / "trained"
S = 384
MEAN = np.tile(np.array([0.485, 0.456, 0.406], np.float32), 2)
STD = np.tile(np.array([0.229, 0.224, 0.225], np.float32), 2)


def mask_path(p: Path):
    return p.with_name(p.name.replace(".png", ".mask.png"))


def load_mask(p: Path, dataset: str):
    m = np.array(Image.open(mask_path(p)).convert("L"))
    return (m > 127).astype(np.uint8) if dataset == "casia_v2" else (m > 90).astype(np.uint8)   # Columbia masks are 3-level grey maps


def build_cache(dataset):
    """uint8 memmaps of [RGB, multi-quality ELA] resized to SxS, plus ground-truth masks (zeros for authentic images)."""
    cache = HERE / "cache"
    cache.mkdir(exist_ok=True)
    xf, mf, meta = cache / f"loc_{dataset}_x.u8", cache / f"loc_{dataset}_m.u8", cache / f"loc_{dataset}_meta.json"
    items = INDEXES[dataset]()
    n = len(items)
    if meta.exists() and json.loads(meta.read_text())["n"] == n:
        return np.memmap(xf, np.uint8, "r", shape=(n, S, S, 6)), np.memmap(mf, np.uint8, "r", shape=(n, S, S)), items
    X = np.memmap(xf, np.uint8, "w+", shape=(n, S, S, 6))
    M = np.memmap(mf, np.uint8, "w+", shape=(n, S, S))
    for i, (p, y, g) in enumerate(items):
        img = Image.open(p).convert("RGB")
        ela = ela_multi(img)                                           # native resolution, before any resizing
        X[i, :, :, :3] = np.asarray(img.resize((S, S), Image.BICUBIC))
        X[i, :, :, 3:] = np.asarray(Image.fromarray(ela).resize((S, S), Image.BILINEAR))
        if y == 1:
            M[i] = np.asarray(Image.fromarray(load_mask(p, dataset) * 255).resize((S, S), Image.NEAREST)) > 127
        else:
            M[i] = 0
        if (i + 1) % 400 == 0:
            print(f"  cache {dataset} {i + 1}/{n}", flush=True)
    X.flush()
    M.flush()
    meta.write_text(json.dumps({"n": n}))
    return X, M, items


class Seg(nn.Module):
    def __init__(self, pretrained=True):
        super().__init__()
        self.enc = timm.create_model("efficientnet_b0.ra_in1k", pretrained=pretrained, features_only=True, in_chans=6, out_indices=(1, 2, 3, 4))
        ch = self.enc.feature_info.channels()
        self.lat = nn.ModuleList([nn.Conv2d(c, 96, 1) for c in ch])
        self.head = nn.Sequential(nn.Conv2d(96, 96, 3, padding=1), nn.BatchNorm2d(96), nn.ReLU(inplace=True), nn.Conv2d(96, 1, 1))

    def forward(self, x):
        fs = self.enc(x)
        y = self.lat[-1](fs[-1])
        for f, l in zip(reversed(fs[:-1]), reversed(self.lat[:-1])):
            y = F.interpolate(y, size=f.shape[-2:], mode="bilinear", align_corners=False) + l(f)
        y = self.head(y)
        return F.interpolate(y, size=x.shape[-2:], mode="bilinear", align_corners=False)


def to_t(xb, dev):
    a = (xb.astype(np.float32) / 255.0 - MEAN) / STD
    return torch.from_numpy(a).permute(0, 3, 1, 2).to(dev)


def dice_loss(logit, y):
    p = torch.sigmoid(logit)
    inter = (p * y).sum((1, 2, 3))
    return (1 - (2 * inter + 1) / (p.sum((1, 2, 3)) + y.sum((1, 2, 3)) + 1)).mean()


@torch.no_grad()
def predict(model, X, idx, dev, bs=16):
    model.eval()
    out = []
    for b in range(0, len(idx), bs):
        x = to_t(np.stack([X[i] for i in idx[b:b + bs]]), dev)
        with torch.autocast("cuda", dtype=torch.float16):
            p = torch.sigmoid(model(x)) + torch.sigmoid(model(x.flip(3))).flip(3)
        out.append((p / 2).float().squeeze(1).cpu().numpy())
    return np.concatenate(out)


def f1_of(pred, gt):
    tp = (pred & gt).sum()
    return 2 * tp / max(1, pred.sum() + gt.sum())


def evaluate(P, M, y, thr, name):
    """Pixel F1 over tampered images (mean per image and pooled), pixel AUC, plus image-level detection from the map."""
    tam = np.where(y == 1)[0]
    per_img = [f1_of(P[i] >= thr, M[i].astype(bool)) for i in tam]
    pooled = f1_of(P[tam] >= thr, M[tam].astype(bool))
    rng = np.random.default_rng(0)
    sel = rng.choice(P[tam].size, size=min(2_000_000, P[tam].size), replace=False)
    auc = roc_auc_score(M[tam].reshape(-1)[sel], P[tam].reshape(-1)[sel])
    best = max((f1_of(P[tam] >= t, M[tam].astype(bool)), t) for t in np.linspace(0.05, 0.95, 19))
    score = np.array([np.sort(P[i].reshape(-1))[-max(1, P[i].size // 100):].mean() for i in range(len(P))])   # mean of the top 1% pixels
    res = {"set": name, "n_tampered": int(len(tam)), "threshold": float(thr), "pixel_f1_mean_per_image": float(np.mean(per_img)),
           "pixel_f1_pooled": float(pooled), "pixel_f1_best_threshold": float(best[0]), "best_threshold": float(best[1]), "pixel_auc": float(auc)}
    if (y == 0).any():
        res["image_auc_from_map"] = float(roc_auc_score(y, score))
    return res, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--bs", type=int, default=12)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    dev = torch.device("cuda")
    OUT.mkdir(parents=True, exist_ok=True)
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    Xc, Mc, ic = build_cache("casia_v2")
    Xm, Mm, im = build_cache("columbia")
    yc = np.array([i[1] for i in ic])
    gc = np.array([i[2] for i in ic])
    tr, va = next(GroupShuffleSplit(1, test_size=0.12, random_state=a.seed).split(np.arange(len(yc)), yc, gc))
    print(f"CASIA: train {len(tr)} / val {len(va)}; Columbia: {len(im)} (test only)", flush=True)
    torch.manual_seed(a.seed)
    rng = random.Random(a.seed)
    model = Seg().to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    steps = a.epochs * ((len(tr) + a.bs - 1) // a.bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps, pct_start=0.1)
    scaler = torch.amp.GradScaler("cuda")
    bce = nn.BCEWithLogitsLoss()
    order = list(tr)
    t0 = time.time()
    best_val, best_state = -1, None
    for ep in range(a.epochs):
        model.train()
        rng.shuffle(order)
        tot = 0
        for b in range(0, len(order), a.bs):
            idx = order[b:b + a.bs]
            x = np.stack([Xc[i] for i in idx])
            m = np.stack([Mc[i] for i in idx])
            if rng.random() < .5:
                x, m = x[:, :, ::-1], m[:, :, ::-1]
            if rng.random() < .5:
                x, m = x[:, ::-1], m[:, ::-1]
            xt = to_t(np.ascontiguousarray(x), dev)
            mt = torch.from_numpy(np.ascontiguousarray(m)).float().unsqueeze(1).to(dev)
            with torch.autocast("cuda", dtype=torch.float16):
                lg = model(xt)
                loss = bce(lg.float(), mt) + dice_loss(lg.float(), mt)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot += loss.item() * len(idx)
        if (ep + 1) % 3 == 0 or ep + 1 == a.epochs:
            Pv = predict(model, Xc, va, dev)
            rv, _ = evaluate(Pv, Mc[va], yc[va], 0.5, "CASIA v2.0 validation")
            sel = rv["pixel_f1_pooled"]
            if sel > best_val:
                best_val, best_state = sel, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            print(f"epoch {ep + 1}/{a.epochs} loss {tot / len(order):.4f}  val pooled F1@0.5 {sel:.4f}  AUC {rv['pixel_auc']:.4f}  ({time.time() - t0:.0f}s)", flush=True)
        else:
            print(f"epoch {ep + 1}/{a.epochs} loss {tot / len(order):.4f}", flush=True)
    model.load_state_dict(best_state)       # checkpoint chosen on CASIA validation only
    Pv = predict(model, Xc, va, dev)
    # threshold chosen on CASIA validation, then applied unchanged to Columbia
    thr = max((f1_of(Pv[yc[va] == 1] >= t, Mc[va][yc[va] == 1].astype(bool)), t) for t in np.linspace(0.1, 0.9, 17))[1]
    rv, sv = evaluate(Pv, Mc[va], yc[va], thr, "CASIA v2.0 validation (held out, source-disjoint)")
    ym = np.array([i[1] for i in im])
    Pm = predict(model, Xm, np.arange(len(ym)), dev)
    rm, sm = evaluate(Pm, Mm, ym, thr, "Columbia (cross-dataset, never used in training)")
    res = {"protocol": "train on CASIA v2.0, test on Columbia (as GIFT, Chen et al. 2026)", "epochs": a.epochs, "threshold_from_casia_validation": float(thr),
           "casia_validation": rv, "columbia": rm,
           "gift_reported": {"columbia_f1": {"GIFT": 0.6497, "E-GIFT": 0.6558, "MFCN": 0.6040, "Edge-enhanced MFCN": 0.6117, "SFCN": 0.5820},
                             "casia_v1_f1": {"GIFT": 0.5728, "E-GIFT": 0.6210}, "casia_v1_auc": {"GIFT": 0.888, "E-GIFT": 0.883, "EVP": 0.862}}}
    (OUT / "localizer_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    torch.save({"state_dict": model.state_dict(), "threshold": float(thr), "size": S}, WEIGHTS / "localizer_effnet_b0.pt")
    np.savez_compressed(OUT / "localizer_columbia_preds.npz", P=(Pm * 255).astype(np.uint8)[:, ::2, ::2], y=ym)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
