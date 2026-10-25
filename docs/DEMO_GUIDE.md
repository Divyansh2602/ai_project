# TrustSphere AI: demonstration guide

What to show, in what order, what each result means, what we tried, why, and what worked best.
All numbers are out-of-fold or held-out (the model never scored an image it trained on), except where a line says "development split".

## 1. One-minute story

> Photos are used as evidence, and editing tools make splicing easy. TrustSphere AI takes an image and answers two questions:
> **Is it authentic or manipulated?** and **can anyone later prove which file was checked and that the record was not changed?**
> Three agents (metadata, image forensics, provenance) each give a score; a decision engine fuses them into Authentic, Fake or Inconclusive.
> The image-forensics agent uses a network we trained: an EfficientNet-B0 that reads error-level-analysis maps. Every result is hashed (SHA-256), signed (Ed25519),
> recorded with a chain of custody, optionally anchored on a blockchain testnet and exported as an evidence PDF.
> On CASIA v2.0 it reaches 95.5% accuracy (95.3% when each tampered image is kept with its source), and 96.4% on 588 images the model never saw.

## 2. Demonstration order (about 10 minutes)

1. **Web app (3 min).** Double-click `START_APP.bat` (opens `http://127.0.0.1:8000/app/`, or the next free port). Use an image from *outside* CASIA for the live upload
   (the app's default model trained on all of CASIA, so a CASIA image proves nothing about accuracy). Show: Analyze page, the verdict gauge, agent breakdown (ELA and Grad-CAM heatmaps),
   evidence chain (hash, signature, chain of custody), evidence PDF, History, How it works.
2. **Results notebook (5 min).** Open `TrustSphere_Results.ipynb` in VS Code (outputs are already saved; Run All is optional). Walk through it with section 3 below.
3. **Report (1 min).** `docs/report/TrustSphere_AI_Project_Report.docx`: architecture and UML diagrams, the full method, the results and the 50 references.

Before a live demo: if `backend/.env` has `POLYGON_PRIVATE_KEY` set, each analysis will try to anchor on the Polygon Amoy testnet (free test tokens, needs internet, adds seconds). Blank it to skip anchoring.

## 3. The notebook, cell by cell

**Section 1, Setup.** Finds the repository, loads `docs/evaluation/metrics.json`. Say: "Everything in this notebook is computed from saved out-of-fold predictions, so it runs without the datasets or a GPU."

**Section 2, Experiments.** Five experiments:

| Experiment | What it tests |
|---|---|
| CASIA v2.0, random 5-fold | normal cross-validation, 2,819 images (1,536 authentic, 1,283 tampered) |
| CASIA v2.0, source-disjoint 5-fold | each tampered image stays in the same fold as the authentic image it was made from, so the model cannot memorise sources |
| Columbia, whole image (ELA) | the same detector on Columbia's uncompressed photos, 363 images |
| Columbia, patch-based (SRM), random | small patches on noise-residual input |
| Columbia, patch-based (SRM), scene-disjoint | same, but all photos of one scene stay in one fold |

**Section 3, Summary table and two bar charts.**

| Experiment | Accuracy | Precision | Recall | F1 | ROC AUC | EER |
|---|---|---|---|---|---|---|
| CASIA random | 95.53% | 95.16% | 95.01% | 95.09% | 0.9917 | 4.58% |
| CASIA source-disjoint | 95.32% | 95.28% | 94.39% | 94.83% | 0.9933 | 4.47% |
| Columbia whole image | 87.60% | 84.26% | 92.22% | 88.06% | 0.9610 | 11.85% |
| Columbia patch, random | 97.25% | 96.70% | 97.78% | 97.24% | 0.9872 | 2.48% |
| Columbia patch, scene-disjoint | 96.97% | 96.69% | 97.22% | 96.95% | 0.9799 | 2.76% |

How to read it: *accuracy* = share correct; *precision* = of images called manipulated, how many truly were; *recall* = of truly manipulated images, how many we caught;
*F1* balances the two; *ROC AUC* = chance that a random manipulated image scores higher than a random authentic one (1.0 perfect, 0.5 coin flip), independent of the threshold;
*EER* = the error rate at the point where false alarms equal misses (lower is better). The last column of the notebook table ("Matches saved metrics.json") shows the numbers are recomputed and agree with the stored ones.
Key message: **CASIA is about 95.5%; Columbia is hard for the ELA detector (87.6%) but a patch-based noise detector fixes it (97%).**

**Section 4, four plots for each experiment.**
- *Confusion matrix* (rows = truth, columns = prediction). CASIA random: 1,474 authentic correct, 62 authentic wrongly flagged, 64 tampered missed, 1,219 tampered caught. Source-disjoint: 1,476 / 60 / 72 / 1,211.
  Columbia ELA: 152 / 31 / 14 / 166. Columbia patch random: 177 / 6 / 4 / 176; scene-disjoint: 177 / 6 / 5 / 175.
- *ROC curve*: the closer to the top-left corner, the better; the red dot is the EER. CASIA curves hug the corner (AUC 0.99).
- *Precision-recall curve*: stays near 1.0 until very high recall, so the detector rarely trades precision for recall.
- *Score distribution* (log scale): authentic scores pile up near 0, manipulated near 1, with a small overlap in the middle. That overlap is exactly where the errors come from and why the final system has an "Inconclusive" band.

Say about random vs source-disjoint: "95.5% vs 95.3%. Keeping sources apart barely changes the result, so the model learned forgery traces, not memorised source images."

**Section 5, per-fold accuracy.** Shows stability. CASIA random: 95.9, 95.4, 96.8, 94.2, 95.4; source-disjoint: 94.0, 96.3, 95.4, 95.9, 95.0 (spread under 1 point).
Columbia ELA: 95.9, 84.9, 84.9, 84.7, 87.5 (unstable, so we changed approach); patch random: 97.3, 93.2, 98.6, 98.6, 98.6; scene-disjoint: 93.0, 100.0, 97.4, 95.7, 98.6.
Say: "Columbia has only 363 images, so each fold has about 73 and results move by several points. That is why we also quote AUC."

**Section 6, full pipeline on held-out images.** 588 CASIA images (301 authentic, 287 tampered) from an 80/20 split; the model trained on the other 80%. The real agents and the decision engine ran on every file.

| | called Authentic | Inconclusive | called Fake |
|---|---|---|---|
| truly authentic (301) | 251 | 42 | 8 |
| truly tampered (287) | 3 | 14 | 270 |

- The engine decides 90.5% of images; **accuracy on decided images 97.9%**; counting Inconclusive as wrong 88.6%.
- Authentic called Fake: 2.7%. Tampered called Authentic: 1.0%.
- Forced to choose (score below 0.5 = Fake): 96.43% accuracy, AUC 0.9943, EER 3.05%. The detector alone: 96.26%, AUC 0.9943.
- Why most "Inconclusive" are authentic images: the metadata agent gives PNG files without EXIF a neutral score (about 0.45), pulling the fused score to the middle. That is a known weakness and is listed in future work.
- The ROC plot shows the detector alone and the fused engine overlapping: the other agents do not hurt the detector, they add evidence and the abstain option.

**Section 7, localisation (say this one honestly).** A U-Net-style network trained on CASIA to outline the tampered region, tested on Columbia, which it never saw:
CASIA validation pixel F1 0.889 (pixel AUC 0.957); Columbia pixel F1 **0.433** (AUC 0.674). The GIFT paper reports 0.6497 on Columbia, so **we are below it**. Reason: it learned JPEG-compression traces of CASIA, which uncompressed Columbia photos do not have.
The verdict does not use this model; heatmaps are supporting evidence only.

**Section 8, comparison with the base papers.** Only results we exceed, on the same dataset and metric:

| Paper | Reported | Ours |
|---|---|---|
| Ravula and Singh 2025 | 94.4% (CASIA v2) | 95.53% / 95.32% |
| Rehman and Jain 2025 | 93.57% (CASIA v2.0) | 95.53% / 95.32% |
| Deb and Kar 2026 | precision/recall/F1 87.31 / 90.15 / 88.33 | 95.16 / 95.01 / 95.09 |
| earlier Columbia methods listed in Ranjan 2026 | 91% to 93.4% | 97.25% / 96.97% (patch-based) |

Say: "Protocols differ between papers (splits, subsets), so this is context, not a leaderboard." The full comparison, including what we do not beat, is in `docs/evaluation/EVALUATION.md`.

**Section 9, sample outputs.** The picture shows, for held-out images, the input, the ELA map and the Grad-CAM attention map; the printed lines show the verdict, authenticity score and manipulation type from the pipeline's JSON.

**Section 10, live detector.** Six random held-out images (3 authentic, 3 tampered) with: the image; the ELA map the network actually sees (JPEG qualities 70, 85, 95 as red, green, blue channels, so recompressed regions glow differently); the ground-truth mask; and the model's probability. Result: **6 of 6 correct**. (Six is a small sample, so quote the full numbers from sections 3 and 6 as the evidence, and treat this as an illustration.)
Set `MY_IMAGE` to a photo to test it live.

**Section 11, honest reading.** The summary of strengths and limits (below).

## 4. Our approaches: what, why, result, verdict

| # | Approach | Why we tried it | Result | Verdict |
|---|---|---|---|---|
| 1 | **Multi-agent pipeline** (metadata, image, provenance) + weighted decision engine with an Inconclusive band | no single signal is reliable (metadata can be stripped, ELA can be fooled, most images have no provenance); a wrong verdict has real cost | 97.9% accuracy on decided images, 90.5% coverage | **Kept** (the system design) |
| 2 | **ELA at one JPEG quality (90)** into EfficientNet-B0 | ELA is a classic forgery cue: a pasted region has a different compression history | development split: 95.28% | works, not the best |
| 3 | **ELA at three qualities (70, 85, 95) stacked as 3 channels ("multiq")** | different qualities expose different traces; costs nothing extra | development split: **95.87%, AUC 0.9955** (best of the inputs); cross-validated 95.53% | **Chosen** (the deployed detector) |
| 4 | RGB + ELA (6 channels) | give the network colour context as well | clearly worse on the development split | dropped |
| 5 | Bigger backbone (EfficientNet-B3) | more capacity | development split: 94.69% (worse than B0 at 95.87%) | dropped; small data favours the small model |
| 6 | Native-resolution 224 x 224 crops, averaged over up to 6 crops (not resizing the whole image) | resizing destroys the high-frequency forensic traces | used in all detectors | **Kept** |
| 7 | Patch-based detector on CASIA (128 px patches, image score = mean of top 5% patch probabilities) | works well for small datasets and localised edits | CASIA 90.0% | worse than whole-image on CASIA; dropped for CASIA |
| 8 | Whole-image detector on Columbia (ELA, or SRM noise residuals) | reuse the CASIA recipe | ELA 87.60%; SRM 86.49% | weak: Columbia photos are uncompressed, so ELA has little to show, and 363 images are few |
| 9 | **Patch-based detector on SRM noise-residual filters for Columbia** | noise statistics survive without a JPEG history; many patches per image give far more training samples | **97.25% random, 96.97% scene-disjoint** | **Chosen for Columbia** (best on Columbia) |
| 10 | U-Net-style localiser (EfficientNet-B0 encoder, RGB + ELA) | follow the GIFT protocol (train on CASIA, test on Columbia) | CASIA 0.889, Columbia 0.433 (GIFT 0.6497) | **below the paper**; reported as a limit |
| 11 | Evidence layer: SHA-256, Ed25519 signature, chain of custody, optional blockchain anchor, PDF | a score alone cannot prove which file was analysed or that the record was not changed | tamper test: altering a stored file is detected | **Kept** (what the base papers do not offer) |

**How we chose, and why it is fair.** The input, backbone and learning rate were selected on a *development split of CASIA only* (the "development split" numbers above). Those numbers were never compared with any paper.
The numbers we report are out-of-fold (every image is scored by a model that did not train on it) or from a held-out 20%.
We reported two stricter splits on purpose: source-disjoint on CASIA and scene-disjoint on Columbia.

**What is best, in one line each**
- Best detector for CASIA: **EfficientNet-B0 on multi-quality ELA** (95.5%).
- Best detector for Columbia: **patch-based on SRM noise residuals** (about 97%).
- Best overall design: the **multi-agent pipeline with the Inconclusive band plus the signed evidence record**.

## 5. Strengths and limits to state yourself

Strengths: out-of-fold evaluation with two leakage-aware protocols; the result barely changes under them; a working web app with evidence PDF and verification; tamper test passes (19 of 19 end-to-end checks).

Limits (say them before the guide asks):
1. Localisation on Columbia (F1 0.43) is below the published 0.65.
2. Some published CASIA results are higher (96% to 99% on the web, under protocols we could not check); we do not claim to be the best.
3. Columbia has only 363 images, so folds swing by several points; its patch threshold is set from the other folds' scores, which came from models that saw the test fold, so the threshold-free AUC (0.98) is the safer figure.
4. The deployed app uses the CASIA detector; the Columbia models are for evaluation only.
5. All data are splicing-style forgeries; fully AI-generated images, screenshots and heavy re-compression were not evaluated.
6. EXIF-free PNGs push the fused score towards Inconclusive.

## 6. Likely questions and short answers

- **"Is 95% good?"** It is above the CASIA numbers of three of the five base papers (94.4%, 93.57%, F1 88.33) and level with the fourth (95.2%, pooled over three datasets). Some web results are higher; protocols differ.
- **"Could it have memorised the images?"** We tested exactly that: keeping each tampered image with its source gives 95.3% vs 95.5%.
- **"Why ELA?"** Cheap, interpretable, and a pasted region often has a different JPEG history. We stacked three qualities because it gave the best development-split result.
- **"Why a different model for Columbia?"** Columbia is uncompressed, so ELA has little signal; noise residuals do. Patches also multiply the tiny dataset.
- **"Why Inconclusive?"** A wrong automatic verdict can accuse an innocent person or clear a forgery; abstaining and sending to a human is safer. It costs about 10% coverage.
- **"What is novel?"** The combination: a trained detector inside a multi-agent pipeline with a signed, verifiable evidence record, plus leakage-aware evaluation. The base papers stop at a label or a mask.
- **"What does the blockchain add?"** Only the hash, verdict and time go on-chain, giving an independent timestamp; the signature and chain of custody carry the rest.
- **"Why is localisation weak?"** It learned CASIA's compression traces; Columbia has none. We report it rather than hide it, and the verdict does not depend on it.
