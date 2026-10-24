"""Patch-based manipulation detector: EfficientNet-B0 on 128 x 128 crops labelled from the ground-truth splice masks.

Small benchmarks (Columbia has 363 images) are too small to train a whole-image network, so the network is trained on patches:
a patch is positive when at least half of it lies inside the spliced region and negative when it contains no spliced pixel (this uses the
masks distributed with the datasets). At test time every image is covered by a dense grid of patches and the image score is the mean of the
highest 5 % patch probabilities. Cross-validation is over images, exactly as for the whole-image detector, and the decision threshold of each
fold is chosen on the out-of-fold scores of the OTHER folds, so the held-out images never influence it.

    python training/train_patch_detector.py --dataset columbia --input srm
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
from PIL import Image
from sklearn.model_selection import GroupKFold, StratifiedKFold

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import CHANNELS, INDEXES, INPUTS, metrics  # noqa: E402
from train_localizer import load_mask  # noqa: E402

REPO = HERE.parent
OUT = REPO / "docs" / "evaluation" / "training"
WEIGHTS = REPO / "backend" / "models" / "trained"
P = 128
MEAN6 = np.tile(np.array([0.485, 0.456, 0.406], np.float32), 2)
STD6 = np.tile(np.array([0.229, 0.224, 0.225], np.float32), 2)


def load_all(dataset, kind):
    items = INDEXES[dataset]()
    maps, masks = [], []
    for i, (p, y, g) in enumerate(items):
        img = Image.open(p)
        m = INPUTS[kind](img)
        maps.append(m)
        masks.append(load_mask(p, dataset) if y == 1 else np.zeros(m.shape[:2], np.uint8))
        if (i + 1) % 100 == 0:
            print(f"    maps {i + 1}/{len(items)}", flush=True)
    return items, maps, masks


def sample_batch(maps, masks, y, idx, bs, rng):
    xs, ls = [], []
    pos_imgs = [i for i in idx if y[i] == 1]
    while len(xs) < bs:
        want_pos = len(xs) % 2 == 0
        if want_pos:
            i = rng.choice(pos_imgs)
            ys_, xs_ = np.nonzero(masks[i])
            if len(ys_) == 0:
                continue
            k = rng.randrange(len(ys_))
            cy, cx = ys_[k], xs_[k]
            y0 = int(np.clip(cy - rng.randint(P // 4, 3 * P // 4), 0, maps[i].shape[0] - P))
            x0 = int(np.clip(cx - rng.randint(P // 4, 3 * P // 4), 0, maps[i].shape[1] - P))
            if masks[i][y0:y0 + P, x0:x0 + P].mean() < 0.5:
                continue
            lab = 1
        else:
            i = rng.choice(idx)
            h, w = masks[i].shape
            y0, x0 = rng.randint(0, h - P), rng.randint(0, w - P)
            if masks[i][y0:y0 + P, x0:x0 + P].any():
                continue
            lab = 0
        c = maps[i][y0:y0 + P, x0:x0 + P]
        if rng.random() < .5:
            c = c[:, ::-1]
        if rng.random() < .5:
            c = c[::-1]
        xs.append(np.ascontiguousarray(c))
        ls.append(lab)
    return np.stack(xs), np.array(ls, np.float32)


def to_t(x, dev, ch):
    a = (x.astype(np.float32) / 255.0 - MEAN6[:ch]) / STD6[:ch]
    return torch.from_numpy(a).permute(0, 3, 1, 2).to(dev)


def train(maps, masks, y, idx, dev, steps, bs, lr, seed, ch, init=None):
    rng = random.Random(seed)
    torch.manual_seed(seed)
    m = timm.create_model("efficientnet_b0.ra_in1k", pretrained=True, num_classes=1, in_chans=ch).to(dev)
    if init is not None:
        m.load_state_dict(init)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.1)
    scaler = torch.amp.GradScaler("cuda")
    lossf = nn.BCEWithLogitsLoss()
    m.train()
    run = 0.0
    for s in range(steps):
        xb, yb = sample_batch(maps, masks, y, idx, bs, rng)
        with torch.autocast("cuda", dtype=torch.float16):
            loss = lossf(m(to_t(xb, dev, ch)).squeeze(1), torch.from_numpy(yb).to(dev))
        opt.zero_grad(set_to_none=True)
        if not torch.isfinite(loss):          # skip a bad step instead of poisoning the weights
            sched.step()
            continue
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        sched.step()
        run = 0.98 * run + 0.02 * loss.item() if s else loss.item()
        if (s + 1) % 250 == 0:
            print(f"    step {s + 1}/{steps} loss {run:.4f}", flush=True)
    return m


@torch.no_grad()
def score_images(model, maps, idx, dev, ch, stride=64, top=0.05):
    model.eval()
    out = []
    for i in idx:
        a = maps[i]
        h, w, _ = a.shape
        if h < P or w < P:
            a = np.pad(a, ((0, max(0, P - h)), (0, max(0, P - w)), (0, 0)), mode="reflect")
            h, w, _ = a.shape
        ys = list(range(0, h - P + 1, stride)) or [0]
        xs = list(range(0, w - P + 1, stride)) or [0]
        if ys[-1] != h - P:
            ys.append(h - P)
        if xs[-1] != w - P:
            xs.append(w - P)
        crops = np.stack([a[y0:y0 + P, x0:x0 + P] for y0 in ys for x0 in xs])
        ps = []
        for b in range(0, len(crops), 128):
            with torch.autocast("cuda", dtype=torch.float16):
                lg = model(to_t(crops[b:b + 128], dev, ch)).squeeze(1).float()
                ps.append(torch.sigmoid(torch.nan_to_num(lg, nan=0.0, posinf=20.0, neginf=-20.0)).cpu().numpy())
        ps = np.sort(np.concatenate(ps))
        k = max(1, int(round(len(ps) * top)))
        out.append(float(ps[-k:].mean()))
    return np.array(out)


def best_threshold(y, s):
    cands = np.unique(np.round(s, 4))
    accs = [((s >= t).astype(int) == y).mean() for t in cands]
    return float(cands[int(np.argmax(accs))])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="columbia")
    ap.add_argument("--input", default="srm", choices=list(INPUTS))
    ap.add_argument("--protocol", default="random", choices=["random", "group"])
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--steps", type=int, default=2500)
    ap.add_argument("--bs", type=int, default=48)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", default="patch")
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    ch = CHANNELS[a.input]
    dev = torch.device("cuda")
    OUT.mkdir(parents=True, exist_ok=True)
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    items, maps, masks = load_all(a.dataset, a.input)
    y = np.array([i[1] for i in items])
    groups = np.array([i[2] for i in items])
    print(f"{a.dataset}: {len(items)} images ({(y == 0).sum()} authentic, {(y == 1).sum()} manipulated), input {a.input}", flush=True)
    split = (StratifiedKFold(a.folds, shuffle=True, random_state=a.seed).split(maps, y) if a.protocol == "random"
             else GroupKFold(a.folds).split(maps, y, groups))
    oof, fold_of = np.zeros(len(items)), np.zeros(len(items), int)
    ckpt = OUT / f"ckpt_{a.dataset}_{a.protocol}_{a.tag}.npz"      # per-fold progress, so an interrupted run resumes
    if ckpt.exists():
        z = np.load(ckpt)
        oof, fold_of = z["oof"], z["fold_of"]
        print(f"resuming: folds done {sorted(set(fold_of.tolist()) - {0})}", flush=True)
    t0 = time.time()
    for f, (tr, te) in enumerate(split, 1):
        if (fold_of[te] == f).all():
            continue
        m = train(maps, masks, y, list(tr), dev, a.steps, a.bs, a.lr, a.seed + f, ch)
        oof[te] = score_images(m, maps, te, dev, ch)
        fold_of[te] = f
        np.savez(ckpt, oof=oof, fold_of=fold_of)
        fm = metrics(y[te], oof[te])
        print(f"fold {f}: acc@0.5 {fm['accuracy']:.4f} auc {fm['roc_auc']:.4f} ({time.time() - t0:.0f}s)", flush=True)
        del m
        torch.cuda.empty_cache()
    folds, pred = [], np.zeros(len(items), int)
    for f in range(1, a.folds + 1):
        te, other = fold_of == f, fold_of != f
        thr = best_threshold(y[other], oof[other])           # threshold from the other folds' out-of-fold scores only
        pred[te] = (oof[te] >= thr).astype(int)
        fm = metrics(y[te], oof[te], thr)
        folds.append({"fold": f, "n_test": int(te.sum()), "threshold": thr, **{k: v for k, v in fm.items() if k != "confusion"}})
    pooled = metrics(y, oof, 0.5)
    pooled_acc = float((pred == y).mean())
    accs = np.array([f["accuracy"] for f in folds])
    pm = metrics(y, pred.astype(float), 0.5)
    res = {"dataset": a.dataset, "protocol": a.protocol, "input": a.input, "patch": P, "steps": a.steps, "aggregation": "mean of top 5% patch probabilities",
           "threshold": "chosen on the other folds' out-of-fold scores", "folds": folds, "mean_fold_accuracy": float(accs.mean()),
           "std_fold_accuracy": float(accs.std()), "pooled_accuracy": pooled_acc, "pooled_out_of_fold": {**pm, "roc_auc": pooled["roc_auc"], "pr_auc": pooled["pr_auc"], "eer": pooled["eer"]}}
    tag = f"{a.dataset}_{a.protocol}_{a.tag}"
    (OUT / f"cv_{tag}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    import pandas as pd
    pd.DataFrame({"file": [i[0].name for i in items], "label": y, "fold": fold_of, "score": oof, "pred": pred}).to_csv(OUT / f"oof_{tag}.csv", index=False)
    print(f"CV {tag}: mean fold accuracy {accs.mean() * 100:.2f} +- {accs.std() * 100:.2f}; pooled acc {pooled_acc * 100:.2f}; AUC {pooled['roc_auc']:.4f}; EER {pooled['eer']:.4f}", flush=True)
    if a.final:
        m = train(maps, masks, y, list(range(len(items))), dev, a.steps, a.bs, a.lr, a.seed, ch)
        thr = best_threshold(y, oof)
        torch.save({"state_dict": m.state_dict(), "backbone": "efficientnet_b0.ra_in1k", "input": a.input, "patch": P, "threshold": thr, "kind": "patch",
                    "dataset": a.dataset}, WEIGHTS / f"{tag}.pt")
        print("saved", WEIGHTS / f"{tag}.pt")


if __name__ == "__main__":
    main()
