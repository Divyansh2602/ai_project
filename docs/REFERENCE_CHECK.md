# Reference check

How the facts and numbers that the report attributes to its references were checked.
The five base papers were read from their PDFs. The other references were checked against their published abstracts and bibliographic records.
The report paraphrases the papers (it does not copy their sentences) but titles, authors, venues and every number match the sources.

## The five base papers (checked in the PDFs)

| Ref | Claim in the report | Where it is in the paper |
|---|---|---|
| [1] Ranjan et al., Franklin Open 16 (2026) 100634 | LOOP texture maps, refined with a pretrained ResNet-50, classified with an SVM | Abstract |
| | Columbia, CASIA v2.0 and a subset of Dresden, stratified 5-fold cross-validation, average accuracy 95.20% | Abstract |
| | Earlier methods that use Columbia, accuracy about 91% to 93.4% | Table 1 (Cozzolino and Verdoliva about 91%, Ghai et al. 93.40%) |
| [2] Ravula and Singh, Intelligent Systems with Applications 26 (2025) 200524 | CoMoFoD 98.95%, MICC-F220 95.2%, CASIA v2 94.4% | Table 4 and the text after Table 3. Note: the paper's abstract gives 99.02% accuracy and 98.95% F1 for CoMoFoD, so the paper is not consistent with itself. The report cites Table 4 and says so. |
| [3] Rehman and Jain, Procedia Computer Science 258 (2025) 3062-3071 | 93.57% without and 98.91% with augmentation on CASIA v2.0 | Results text |
| | Batch 128: accuracy 98.91%, mean 93.39%, std 8.75%. Batch 200: accuracy 93.57%, mean 90.25%, std 7.98%, 10-fold cross-validation | Table 3 |
| [4] Deb and Kar, Procedia Computer Science 283 (2026) 1103-1112 | CASIA V2.0 precision 87.31, recall 90.15, F1 88.33 | Table 4 |
| | Pre-processing, feature extraction, segmentation and localisation; dataset heterogeneity | Abstract |
| [5] Chen et al., J. Vis. Commun. Image R. 118 (2026) 104797 | Pretrained EfficientNet-B4 with multi-level XGBoost, no backpropagation | Sections 1 and 3 |
| | Train on CASIA v2.0, test on CASIA v1.0 and Columbia, following Salloum et al. | Section 4 |
| | GIFT F1 0.5728 (CASIA v1.0) and 0.6497 (Columbia), 18.4M parameters; edge version 0.6210 and 0.6558 | Table 1 |
| | Forgery kinds (splicing, copy-move, removal) and hand-made cues (noise, colour filter array, illumination, double JPEG) | Section 2 |

CASIA v2.0 has 7,491 authentic and 5,123 tampered images in total (GIFT, Section 4.1). The project uses a 2,819 image subset (1,536 authentic, 1,283 tampered)
from the Hugging Face compilation, so the comparison with papers that use the full set is context, not a ranking. The report states this.

## Corrections made during this check

* Rehman and Jain: the mean 93.39% belongs to the 98.91% setting, not to 93.57%. The comparison now uses their mean accuracy over folds (93.39%) and states that their best single figure is 98.91%.
* Huh et al.: the model is trained to judge whether an image is self consistent using EXIF data. It does not predict whether two patches come from the same image.
* MVSS-Net: noise and boundary artifacts are its input views, with multi-scale supervision.
* Bayar and Stamm: a phrase that could not be confirmed ("prediction error filters") was removed.
* Muhammad et al.: the first author is Ghulam Muhammad.
* Hasan and Salah: the authors are Haya R. Hasan and Khaled Salah.
* Dresden database pages are 1584 to 1590 in the SAC 2010 proceedings.
* MVSS-Net is cited by its ICCV 2021 paper, whose details could be confirmed.

## Other references

Titles, authors, venues, volumes and pages of references [6] to [50] were checked against publisher, DBLP, CVF or university repository records.
For CAT-Net and RRU-Net the page range could not be confirmed, so those two are cited by DOI. The Popescu and Farid papers and a few classic works
(Fridrich 2003, ResNet, ViT, U-Net, AdamW) were not re-checked online, so check them against Google Scholar before submission.

## Citation numbering and the automatic check

* References are numbered in the order they are first cited, as in the conference paper. One citation is `[3]`, two are `[3, 4]` and three or more in a row are a range such as `[5-9]`.
* The base papers are cited together in the introduction, so they are references 1 to 5.
* `python scripts/check_citations.py` checks the built report. It confirms that the numbers are serial with no gaps, that groups are written in this style, that every reference is cited and every cited number exists,
  that the reference list is in the same order, and that a name or method written before a citation (for example Mahdian and Saic, BusterNet, CoMoFoD) is the reference that is cited.
  It was also tested on a copy with deliberate mistakes and reported all of them.
* The mapping used for the last build is stored in `docs/report/citation_map.json`.
