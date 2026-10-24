"""Trained image / document-scan manipulation detector: EfficientNet-B0 on error-level-analysis maps.

Evaluated with cross-validation on the dataset itself (like the reference papers) and, for CASIA v2.0, also with a leakage-aware
protocol that keeps each tampered image together with its source image. A final model is then trained on all data for the app.

    python training/train_image_detector.py --dataset casia_v2 --protocol random   --folds 5
    python training/train_image_detector.py --dataset casia_v2 --protocol group    --folds 5
    python training/train_image_detector.py --dataset columbia  --protocol random   --folds 5
    python training/train_image_detector.py --dataset t_sroie   --protocol random   --folds 5 --final

Hyper-parameters were fixed on a single development split of CASIA (see docs/evaluation/TRAINING.md) and are not tuned per fold.
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
from sklearn.model_selection import GroupKFold, StratifiedKFold, train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import CHANNELS, INDEXES, INPUTS, metrics  # noqa: E402

REPO = HERE.parent
OUT = REPO / "docs" / "evaluation" / "training"
WEIGHTS = REPO / "backend" / "models" / "trained"
MEAN, STD = np.tile(np.array([0.485, 0.456, 0.406], np.float32), 2), np.tile(np.array([0.229, 0.224, 0.225], np.float32), 2)
CROP = 224
BACKBONE = "efficientnet_b0.ra_in1k"
IN_CHANS = 3
BACKBONES = {"b0": "efficientnet_b0.ra_in1k", "b3": "efficientnet_b3.ra2_in1k"}


def load_ela(items, kind, dataset):
    """Forensic input maps, cached on disk (training/cache) so repeated runs do not recompute them."""
    cache = HERE / "cache" / f"maps_{dataset}_{kind}.npz"
    if cache.exists():
        z = np.load(cache)
        return [z[str(i)] for i in range(len(items))]
    out = []
    for i, (p, y, g) in enumerate(items):
        out.append(INPUTS[kind](Image.open(p)))
        if (i + 1) % 500 == 0:
            print(f"    maps {i + 1}/{len(items)}", flush=True)
    cache.parent.mkdir(exist_ok=True)
    np.savez(cache, **{str(i): a for i, a in enumerate(out)})
    return out


def crops_of(arr, k, rng=None, train=False):
    """Crops of size CROP. Train: k random crops. Test: a deterministic grid (at most k)."""
    h, w, _ = arr.shape
    if h < CROP or w < CROP:
        arr = np.pad(arr, ((0, max(0, CROP - h)), (0, max(0, CROP - w)), (0, 0)), mode="reflect")
        h, w, _ = arr.shape
    if train:
        res = []
        for _ in range(k):
            y, x = rng.randint(0, h - CROP), rng.randint(0, w - CROP)
            c = arr[y:y + CROP, x:x + CROP]
            if rng.random() < .5:
                c = c[:, ::-1]
            if rng.random() < .5:
                c = c[::-1]
            res.append(c)
        return res
    ys = np.linspace(0, h - CROP, min(k, max(1, (h - CROP) // 64 + 1))).astype(int) if h > CROP else [0]
    xs = np.linspace(0, w - CROP, min(k, max(1, (w - CROP) // 64 + 1))).astype(int) if w > CROP else [0]
    grid = [arr[y:y + CROP, x:x + CROP] for y in ys for x in xs]
    if len(grid) > k:
        idx = np.linspace(0, len(grid) - 1, k).astype(int)
        grid = [grid[i] for i in idx]
    return grid


def to_tensor(crops, dev):
    stack = np.stack([np.ascontiguousarray(c) for c in crops]).astype(np.float32) / 255.0
    ch = stack.shape[-1]
    a = (stack - MEAN[:ch]) / STD[:ch]
    return torch.from_numpy(a).permute(0, 3, 1, 2).to(dev)


def make_model(dev):
    m = timm.create_model(BACKBONE, pretrained=True, num_classes=1, in_chans=IN_CHANS)
    return m.to(dev)


def train_model(arrs, ys, dev, epochs, repeat, bs, lr, seed, val=None, log=""):
    rng = random.Random(seed)
    torch.manual_seed(seed)
    model = make_model(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    steps = epochs * ((len(arrs) * repeat + bs - 1) // bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.15)
    scaler = torch.amp.GradScaler("cuda")
    lossf = nn.BCEWithLogitsLoss()
    order = list(range(len(arrs))) * repeat
    for ep in range(epochs):
        model.train()
        rng.shuffle(order)
        tot, n = 0.0, 0
        for b in range(0, len(order), bs):
            idx = order[b:b + bs]
            crops, lab = [], []
            for i in idx:
                crops += crops_of(arrs[i], 1, rng, True)
                lab.append(ys[i])
            x = to_tensor(crops, dev)
            y = torch.tensor(lab, dtype=torch.float32, device=dev)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = lossf(model(x).squeeze(1), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot += loss.item() * len(idx)
            n += len(idx)
        msg = f"{log} epoch {ep + 1}/{epochs} loss {tot / n:.4f}"
        if val is not None:
            pv = predict(model, val[0], dev)
            msg += f"  val acc {((pv >= .5) == np.array(val[1])).mean():.4f}"
        print(msg, flush=True)
    return model


@torch.no_grad()
def predict(model, arrs, dev, k=6):
    model.eval()
    out = []
    for a in arrs:
        x = to_tensor(crops_of(a, k), dev)
        with torch.autocast("cuda", dtype=torch.float16):
            lg = model(x).squeeze(1).float()
        out.append(float(torch.sigmoid(lg.mean())))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=list(INDEXES))
    ap.add_argument("--protocol", default="random", choices=["random", "group"])
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--repeat", type=int, default=1, help="random crops per image per epoch")
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--input", default="ela90", choices=list(INPUTS))
    ap.add_argument("--tag", default="", help="suffix for output files (lets several runs coexist)")
    ap.add_argument("--backbone", default="b0", choices=list(BACKBONES))
    ap.add_argument("--dev-only", action="store_true", help="one 80/20 development split, no CV")
    ap.add_argument("--final", action="store_true", help="also train and save a final model on all data")
    ap.add_argument("--no-cv", action="store_true")
    ap.add_argument("--holdout", action="store_true", help="train on 80%% (source-disjoint), save weights + the held-out file list for pipeline evaluation")
    a = ap.parse_args()
    global BACKBONE, IN_CHANS
    BACKBONE = BACKBONES[a.backbone]
    IN_CHANS = CHANNELS[a.input]
    dev = torch.device("cuda")
    OUT.mkdir(parents=True, exist_ok=True)
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    items = INDEXES[a.dataset]()
    y = np.array([i[1] for i in items])
    groups = np.array([i[2] for i in items])
    print(f"{a.dataset}: {len(items)} images ({(y == 0).sum()} authentic, {(y == 1).sum()} manipulated)", flush=True)
    arrs = load_ela(items, a.input, a.dataset)

    tag = f"{a.dataset}_{a.protocol}" + (f"_{a.tag}" if a.tag else "")
    if a.holdout:
        from sklearn.model_selection import GroupShuffleSplit
        tr, te = next(GroupShuffleSplit(1, test_size=0.2, random_state=a.seed).split(arrs, y, groups))
        m = train_model([arrs[i] for i in tr], [int(y[i]) for i in tr], dev, a.epochs, a.repeat, a.bs, a.lr, a.seed, log="holdout")
        torch.save({"state_dict": m.state_dict(), "backbone": BACKBONE, "input": a.input, "crop": CROP, "dataset": a.dataset}, WEIGHTS / f"{tag}_holdout.pt")
        p_te = predict(m, [arrs[i] for i in te], dev)
        hm = metrics(y[te], p_te)
        (OUT / f"holdout_{tag}.json").write_text(json.dumps({
            "dataset": a.dataset, "weights": f"{tag}_holdout.pt", "n_train": int(len(tr)), "n_test": int(len(te)),
            "test_files": [str(items[i][0]) for i in te], "test_labels": [int(y[i]) for i in te], "test_p_fake": [float(v) for v in p_te],
            "metrics": hm}, indent=1), encoding="utf-8")
        print(f"HOLDOUT {tag}: n_test {len(te)} acc {hm['accuracy']:.4f} auc {hm['roc_auc']:.4f} eer {hm['eer']:.4f}", flush=True)
        return
    if a.dev_only:
        tr, te = train_test_split(np.arange(len(items)), test_size=0.2, stratify=y, random_state=a.seed)
        tr2, va = train_test_split(tr, test_size=0.15, stratify=y[tr], random_state=a.seed)
        m = train_model([arrs[i] for i in tr2], [int(y[i]) for i in tr2], dev, a.epochs, a.repeat, a.bs, a.lr, a.seed,
                        val=([arrs[i] for i in va], [int(y[i]) for i in va]), log="dev")
        pv = predict(m, [arrs[i] for i in va], dev)
        print("DEV validation:", json.dumps({k: v for k, v in metrics(y[va], pv).items() if k != "confusion"}), flush=True)
        return
    if not a.no_cv:
        split = (StratifiedKFold(a.folds, shuffle=True, random_state=a.seed).split(arrs, y) if a.protocol == "random"
                 else GroupKFold(a.folds).split(arrs, y, groups))
        oof = np.full(len(items), np.nan)
        folds = []
        t0 = time.time()
        for f, (tr, te) in enumerate(split, 1):
            m = train_model([arrs[i] for i in tr], [int(y[i]) for i in tr], dev, a.epochs, a.repeat, a.bs, a.lr, a.seed + f, log=f"fold {f}")
            oof[te] = predict(m, [arrs[i] for i in te], dev)
            fm = metrics(y[te], oof[te])
            folds.append({"fold": f, "n_test": int(len(te)), **{k: v for k, v in fm.items() if k != "confusion"}})
            print(f"fold {f}: acc {fm['accuracy']:.4f} auc {fm['roc_auc']:.4f} eer {fm['eer']:.4f}  ({time.time() - t0:.0f}s)", flush=True)
            del m
            torch.cuda.empty_cache()
        pooled = metrics(y, oof)
        accs = np.array([f["accuracy"] for f in folds])
        res = {"dataset": a.dataset, "protocol": a.protocol, "folds": folds, "backbone": BACKBONE, "input": a.input, "lr": a.lr, "epochs": a.epochs, "crop": CROP,
               "mean_fold_accuracy": float(accs.mean()), "std_fold_accuracy": float(accs.std()), "pooled_out_of_fold": pooled}
        (OUT / f"cv_{tag}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        import pandas as pd
        pd.DataFrame({"file": [i[0].name for i in items], "label": y, "group": groups, "p_fake": oof}).to_csv(OUT / f"oof_{tag}.csv", index=False)
        print(f"CV {tag}: mean fold accuracy {accs.mean() * 100:.2f} +- {accs.std() * 100:.2f}; pooled AUC {pooled['roc_auc']:.4f}, EER {pooled['eer']:.4f}", flush=True)
    if a.final:
        m = train_model(arrs, [int(v) for v in y], dev, a.epochs, a.repeat, a.bs, a.lr, a.seed, log="final")
        torch.save({"state_dict": m.state_dict(), "backbone": BACKBONE, "input": a.input, "crop": CROP, "dataset": a.dataset}, WEIGHTS / f"{tag}.pt")
        print("saved", WEIGHTS / f"{tag}.pt")


if __name__ == "__main__":
    main()
