"""Plain wording for the project report.

build_report.py looks every body paragraph and bullet up here: if the start of the generated text matches a key, the text below is used instead.
Numbers are filled from the saved metrics (the dict N), never typed in by hand.
Citations are written with the numbers of the source reference list, groups as [a-b] or [a, b]. The builder renumbers them in order of first appearance.
"""

TEAM = [("23BCI0065", "Divyansh Gupta"), ("23BCI0160", "Shubham Raj"), ("23BCI0053", "Rudrarka Nath")]
GUIDE = "Manikandan G"
GUIDE_COVER = "MANIKANDAN G"
GUIDE_DESIGNATION = "Assistant Professor Sr. Grade 2"
HOD = "Dr. Rajeshkannan R"
HOD_COVER = "Dr. RAJESHKANNAN R"
SEMESTER = "Fall Semester 2026-2027"
NAMES = "Divyansh Gupta, Shubham Raj and Rudrarka Nath"
NAMES_REG = "Divyansh Gupta (23BCI0065), Shubham Raj (23BCI0160) and Rudrarka Nath (23BCI0053)"

ACK = [
    "We thank Vellore Institute of Technology (VIT) for giving us the chance and the resources to carry out this project and the facilities and support at VIT helped us build and test our ideas.",
    "We sincerely thank Dr. Jaisankar N, Dean of the School of Computer Science and Engineering (SCOPE), for the support and encouragement given to the students of the school which motivated us to do our best work.",
    "We thank Dr. Rajeshkannan R, Head of the Department, for guidance and support during this project and the advice and feedback we received helped us shape the work and solve problems along the way.",
    "We are very thankful to our project guide, Manikandan G, Assistant Professor Sr. Grade 2, for regular guidance and useful feedback and the time given in our reviews helped us improve our methods and finish this work.",
    "Thank you all for your support.",
]


def abstract(N):
    return [
        "Photographs are used as evidence in news, insurance, banking and courts and editing tools make it easy to paste part of one image into another. "
        "Deciding whether an image was changed is one problem and proving later that the decision was not altered is another, so this project builds TrustSphere AI, a system for still images that handles both. "
        "Three agents look at each uploaded image, where a metadata agent reads the EXIF data and an image forensics agent studies the pixels and a provenance agent checks content credentials and invisible watermarks. "
        "A decision engine combines their scores into a verdict of Authentic, Fake or Inconclusive. "
        "Each result is hashed with SHA-256 and signed with Ed25519 and stored with a chain of custody, and it can be anchored on a test blockchain and saved as an evidence PDF while a web application shows the whole process.",
        "The image forensics agent uses a detector that we trained, which is an EfficientNet-B0 network that reads error level analysis maps made at three JPEG qualities from crops at the original resolution. "
        "We trained and tested it on a subset of CASIA v2.0 (1,536 authentic and 1,283 tampered images) and on Columbia (183 authentic and 180 spliced images). "
        f"With 5-fold cross-validation on CASIA v2.0 the accuracy is {N['cr']}% with a random split and {N['cg']}% when each tampered image stays in the same fold as its source, "
        f"and on {N['n']} images that were never used in training it reaches {N['ho']} while the full pipeline gives a verdict on {N['cov']} of them with {N['acc_dec']} accuracy and sends the rest to a person. "
        f"Columbia is harder because its photos are uncompressed, so a whole image detector reaches only {N['ce']}% (mean of the folds), while a patch based detector on noise residuals reaches {N['cp']} with a random split and {N['cpg']} when every scene stays in one fold (accuracy pooled over all folds). "
        f"A model that outlines the tampered area and was trained on CASIA does not work well on Columbia (pixel F1 {N['loc_c']}). "
        "We compare the results with the base papers, list in Chapter 7 the results that we exceed and state the weaknesses as well, and the full comparison is in the project repository.",
    ]


# (start of the generated text without ** marks, replacement)
OVERRIDES = [
    # 1 Introduction
    ("Photographs are accepted as evidence in newsrooms",
     "Photographs are accepted as evidence in newsrooms, insurance claims, banks and courts, yet the same tools that fix a holiday photo can move an object into a scene or remove a person or paste a face onto another body and the result often looks real to the eye. "
     "Image forensics asks whether an image is authentic and passive methods answer this using only the image, by looking for traces that editing leaves behind such as different noise or colour patterns or JPEG compression history between the pasted part and the rest of the picture."),
    ("A second question is just as important",
     "A second question matters just as much, which is whether anyone can prove after an analysis which file was checked and what the verdict was and that the record was not changed. "
     "A detector that only prints a score cannot answer this, so we built the analysis and the evidence record as one system where each run gives a verdict and the evidence behind it, such as scores and heatmaps and reasons, and a record that anyone can check with cryptography."),
    ("Published splicing detectors report accuracies",
     "Published detectors report accuracies above 90% on CASIA v2.0 or Columbia [1-3] but most are research code that gives a label for one dataset and stops, while an analyst needs an application that takes any image and explains its answer."),
    ("A wrong automatic verdict can accuse",
     "A wrong automatic verdict can blame an innocent photographer or clear a fake, so the system should be able to say Inconclusive and pass the image to a person."),
    ("Evidence has to survive scrutiny",
     "Evidence must hold up when it is questioned, and a SHA-256 hash of the exact file together with a digital signature on the record and an optional public timestamp lets a third party check that nothing changed after the analysis."),
    ("No single signal can be trusted alone",
     "No single signal can be trusted alone because metadata is easy to remove and recompression hides ELA traces and most images carry no provenance data, so several agents are used to cover for each other."),
    ("TrustSphere AI analyses still images only",
     "TrustSphere AI analyses still images only, and earlier versions of the project also handled audio and documents but we removed both, so none of their code or data or results appear in this report."),
    ("Included: image upload",
     "**Included:** image upload, a metadata agent, an image forensics agent with a trained detector, a provenance agent, a decision engine, SHA-256 hashing, Ed25519 signing, a chain of custody, optional blockchain anchoring, an evidence PDF, a REST API and a web application."),
    ("Datasets: CASIA v2.0 and Columbia",
     "**Datasets:** CASIA v2.0 and Columbia. CASIA v2.0 is used by all five base papers [1-5] and Columbia by two of them [1, 5]."),
    ("Experiments: image-level detection",
     "**Experiments:** detection accuracy by cross-validation and a test of the full pipeline on held out images and a localisation experiment."),
    ("Not included: video",
     "**Not included:** video, audio, document forensics, training on fully AI generated images and any legal judgement, because the score is meant to support a decision and not replace it."),
    # 2 Literature review
    ("Image forgery falls into three common kinds",
     "Image forgery has three common kinds, which are splicing where a part of one image is pasted into another and copy-move where a part is copied within the same image and removal where an object is erased and the gap is filled [5]. "
     "Classic detectors look for mismatches in noise or colour filter patterns or lighting or double JPEG compression because a pasted part keeps the statistics of its source image [5]. "
     "Error level analysis (ELA) was described for forensic use by Krawetz [10] and it saves an image again as JPEG at a known quality and shows the difference, so parts with a different compression history stand out."),
    ("Deep learning replaced hand-crafted features",
     "Deep learning has replaced hand made features in most recent work, and Salloum et al. [6] trained a fully convolutional network on CASIA v2.0 to predict both the spliced region and its boundary and tested it on CASIA v1.0 and Columbia and other sets, "
     "a way of training on CASIA and testing elsewhere that was later used by [5]."),
    ("Early passive methods rely on physical traces",
     "Early passive methods use traces left by the camera and the editing steps, so scaling or rotating leaves repeating patterns between neighbouring pixels [15] and camera colour interpolation leaves patterns that a pasted part tends to lack [16], "
     "while sensor noise works like a fingerprint of the camera and a region without it may be tampered [17]. Mahdian and Saic look for regions with a different noise level [18]. "
     "For JPEG images, JPEG ghosts show a region first saved at another quality [19] and Bianchi and Piva estimate the chance of tampering for each 8 × 8 block [20]. "
     "Copy-move forgery was first found by matching blocks [21], SIFT keypoints can also give the transformation of the copied region [22] and Christlein et al. compared fifteen feature sets in one pipeline [23]. "
     "Splicebuster models noise residuals and splits the image into real and spliced parts without any forged training examples [24], and the filters of the rich models by Fridrich and Kodovský were made for steganalysis [25] and we use them as the SRM input for Columbia."),
    ("Deep networks learn such traces from data",
     "Deep networks learn these traces from data. Bayar and Stamm put a constraint on the first convolutional layer, so the network ignores what the picture shows and learns the small differences between neighbouring pixels that editing leaves behind [26]. "
     "Zhou et al. pass the picture and a noise version of it through two branches of a Faster R-CNN [27]. "
     "Huh et al. need no forged examples at all, since they train only on real photographs to tell whether two patches carry the same EXIF attributes and then mark the patches that disagree with the rest of the image as a splice [28]. "
     "BusterNet separates the source and target regions of copy-move forgery [29] and ManTra-Net learns many manipulation types and treats localisation as finding anomalies [30], while RRU-Net adds residual feedback to a U-Net [31] and PSCC-Net predicts masks step by step at several scales [32]. "
     "MVSS-Net learns from the noise view and from boundary artifacts and is supervised at several scales [33], CAT-Net learns from JPEG DCT coefficients and pixels [34], ObjectFormer uses RGB and high frequency features in a transformer [35] and TruFor adds a learned noise fingerprint and a reliability map [36]. "
     "Most of these papers are judged on how well they locate the tampered pixels but our detector answers the image level question of authentic or tampered, which is the same question that the base papers [1-4] answer."),
    ("Surveys of the field are given in",
     "Surveys are given in [37-40], where Verdoliva covers media forensics and deepfakes and Qureshi and Deriche list pixel based blind methods and Stamm et al. describe the first ten years of information forensics and Warif et al. review copy-move detection. "
     "Muhammad et al. tell authentic from tampered images using a steerable pyramid transform and local binary patterns on the colour channels [41]. "
     "Besides CASIA [7] and the Columbia splicing set [8], other datasets in this field are the Columbia set of authentic and spliced blocks [42] and CoMoFoD [43] and COVERAGE [44] and the Dresden image database [45]. "
     "Our building blocks are standard, since residual networks [46] and vision transformers [47] are common alternatives to our EfficientNet backbone [9] and the localiser follows the U-Net layout [48] and training uses AdamW [49]. "
     "For evidence, Hasan and Salah used Ethereum smart contracts to track where a media file came from using file hashes [50] and we store a SHA-256 hash of the analysed image in a similar way and add a signature and a chain of custody."),
    ("The five base papers of this project are summarised next",
     "The five base papers of this project are summarised next."),
    ("Ranjan et al. combine a local optimal",
     "Ranjan et al. extract texture maps with the Local Optimal Oriented Pattern (LOOP) and refine them with a pretrained ResNet-50 and classify with an SVM, testing on the Columbia splicing dataset and CASIA v2.0 and a part of the Dresden image database using stratified 5-fold cross-validation with an average accuracy of 95.20%. "
     "Their review table lists earlier methods that use Columbia with accuracies between about 91% and 93.4%."),
    ("Ravula and Singh detect and classify",
     "Ravula and Singh detect and classify copy-move forgery using generative adversarial networks and a vision transformer and spectral clustering together. "
     "In their Table 4 they report accuracy of 98.95% on CoMoFoD and 95.2% on MICC-F220 and 94.4% on CASIA v2, while their abstract gives 99.02% accuracy for CoMoFoD."),
    ("Rehman and Jain extract patch descriptors",
     "Rehman and Jain take patch features from a pretrained CNN and fuse them and classify with an SVM, and on CASIA v2.0 they report 93.57% accuracy without augmentation and 98.91% with augmentation. "
     "Their Table 3 uses 10-fold cross-validation and gives accuracy 98.91% with mean 93.39% and standard deviation 8.75% for batch size 128, and accuracy 93.57% with mean 90.25% and standard deviation 7.98% for batch size 200."),
    ("Deb and Kar propose a CNN-based",
     "Deb and Kar propose a CNN based copy-move method with preprocessing and feature extraction and segmentation and localisation steps and they also study how different the datasets are. "
     "On CASIA v2.0 they report precision 87.31 and recall 90.15 and F1 88.33."),
    ("Chen et al. extract features from a frozen",
     "Chen et al. take features from a pretrained EfficientNet-B4 and train XGBoost models at several levels for the splicing mask and a second version also predicts the mask boundary, so no backpropagation is needed. "
     "Following [6] they train on CASIA v2.0 and test on CASIA v1.0 and Columbia and they report pixel F1 of 0.5728 (0.6210 with edges) on CASIA v1.0 and 0.6497 (0.6558) on Columbia, with 18.4 million parameters for GIFT."),
    ("Evaluation that may reward memorisation",
     "**Tests may reward memory** because CASIA v2.0 has tampered images made from authentic images in the same set, so a random split can put a tampered image in the test set and its source in the training set. "
     "The base papers report random split or cross-validation accuracy and do not say if sources were kept apart, but we report both a random split and a split that keeps sources together."),
    ("Detection without evidence",
     "**Detection happens without evidence** since the base papers stop at a label or a mask and none of them hashes the file or signs the result or gives a record that a third party can check."),
    ("Prototypes, not applications",
     "**The published methods are prototypes** and not applications because they are scripts for one benchmark, so an analyst gets no upload page and no explanation of the verdict and no way to review earlier cases."),
    ("Weak transfer",
     "**Transfer is weak** since the protocol of [5, 6] trains on CASIA v2.0 and tests on Columbia and gives pixel F1 of about 0.65 at best, so behaviour on a new dataset is still an open problem and a system should say so."),
    ("Build a multi-agent pipeline",
     "Build a multi-agent pipeline with metadata, image forensics and provenance agents and a decision engine that returns Authentic, Fake or Inconclusive with reasons."),
    ("Train an image manipulation detector",
     "Train an image manipulation detector on CASIA v2.0 and Columbia and measure it with cross-validation, including a split that keeps sources together."),
    ("Make every analysis tamper-evident",
     "Make every analysis tamper evident with a SHA-256 hash, an Ed25519 signature, a chain of custody, an optional blockchain anchor and an evidence PDF."),
    ("Deliver a web application and REST API",
     "Build a web application and REST API that run on one machine."),
    ("Compare the results with the five base papers",
     "Compare the results with the five base papers on the same datasets and say where the system falls short."),
    ("Given a still image of unknown origin",
     "Given a still image of unknown origin, decide whether it is authentic or manipulated and show the evidence for the decision, and say Inconclusive when the evidence is weak while keeping a record of the analysis that a third party can check without trusting the operator."),
    ("The plan follows the history of the project repository",
     "The plan follows the history of the project repository and the dates are the dates of the work, while the training and evaluation work of October 2026 was done in this semester."),
    # 3 Technical specification
    ("FR1. Accept an uploaded image",
     "FR1. Accept an uploaded image (JPEG, PNG, WebP, GIF, BMP or TIFF) up to 100 MB and reject every other file type with HTTP 415."),
    ("FR3. Run the metadata",
     "FR3. Run the metadata, image forensics and provenance agents and store what each agent finds."),
    ("FR4. Fuse the agent scores",
     "FR4. Combine the agent scores into an authenticity score between 0 and 1 and a verdict, where Authentic is at or above 0.75 and Fake is at or below 0.40 and anything between is Inconclusive."),
    ("FR5. Show the reasoning",
     "FR5. Show the reasons and the heatmaps (error level analysis and Grad-CAM [11]) and how much each metadata field contributed."),
    ("FR6. Sign every record",
     "FR6. Sign every record with Ed25519 and keep a chain of custody and, if a wallet is set, anchor the verdict on the Polygon Amoy blockchain."),
    ("FR7. Generate an evidence PDF",
     "FR7. Create an evidence PDF and let anyone check the file hash and the signature and the anchor again."),
    ("FR8. Provide a web application",
     "FR8. Provide a web application and a documented REST API."),
    ("Accuracy and honesty",
     "**Accuracy:** only cross-validated and held out figures are reported, with the protocol stated."),
    ("Performance: analyse one image",
     "**Speed:** analyse one image in seconds on one GPU. On the 588 held out images the three agents and the decision engine took 0.24 s per image on average (about 142 s in total), and this does not include upload, signing, PDF creation or loading the model for the first time, which is why a full request through the web application takes several seconds (Table 5.1)."),
    ("Integrity: any change",
     "**Integrity:** any change to a stored file or record must be detectable."),
    ("Portability: run on one Windows",
     "**Portability:** run on one Windows machine with SQLite and no Redis and also with PostgreSQL and Redis."),
    ("Security: signing keys",
     "**Security:** signing keys, wallet keys and environment files are never committed to the repository."),
    ("Maintainability: each agent",
     "**Maintainability:** each agent is one module with the same interface, so one agent can be replaced without touching the others."),
    ("Every component is available as open-source",
     "Every part is available as open source software (Python, PyTorch, timm, FastAPI, SQLAlchemy, ReportLab and web3) and the detector is small, since EfficientNet-B0 has about 4 million parameters and we trained and tested it on one laptop GPU with 8 GB of memory. "
     "We start from pretrained ImageNet weights, so no large dataset or cluster is needed."),
    ("No paid service was used",
     "No paid service was used because the models and libraries are open source and the datasets are public, and the database is SQLite or a free PostgreSQL plan while blockchain anchoring uses the Polygon Amoy test network where gas is free. "
     "The only hardware is the development laptop, so the running cost is only electricity."),
    ("The system supports journalists",
     "The system helps journalists and insurers and investigators sort images, and the main risk is trusting an automatic verdict too much, so the design adds an Inconclusive band and visible reasons and heatmaps and a note that scores are not a legal finding. "
     "Images are processed on the operator's own machine and are not sent to anyone else."),
    # 4 Design
    ("The user uploads an image through the web application",
     "The user uploads an image in the web application and the FastAPI backend stores the file, hashes it and runs three agents. Each agent returns a score from 0 (fake) to 1 (authentic) and a list of findings. "
     "The decision engine takes the weighted average of the scores with weights of 0.30 for image forensics and 0.25 for provenance and 0.20 for metadata, and an agent with no signal is left out instead of being counted as 0.5. "
     "The average becomes a verdict and the record is then signed and saved in the database with a chain of custody and anchored on the blockchain if set up, and it is made available as JSON and as an evidence PDF."),
    ("Figure 4.2 shows the level-1 data flow",
     "Figure 4.2 shows the level 1 data flow, where the original file and its hash go to the evidence store and the forensic agents read the trained model weights and the signed record goes back to the store and the report goes to the analyst."),
    ("The analyst uploads images, reads verdicts",
     "The analyst uploads images, reads verdicts and heatmaps, downloads the evidence PDF and browses the history, and a verifier or auditor does not have to trust the analyst because the verdict and the evidence PDF and the integrity check are open to anyone who has the file identifier."),
    ("The data model has four tables",
     "The data model has four tables, where Evidence holds the uploaded file, AgentResult has one row per agent, FinalVerdict has one row per analysis and AuditLog holds the signature, the anchor and the chain of custody. "
     "All agents use the same run(path) interface, so the decision engine treats them the same way."),
    ("Figure 4.6 shows one analysis from upload",
     "Figure 4.6 shows one analysis from upload to report, and report and verification are separate requests so verification can be repeated at any later time."),
    # 5 Methodology
    ("The upload endpoint accepts only image MIME types",
     "The upload endpoint accepts only image MIME types, the file is saved under its SHA-256 hash, a database row is created and the analysis is queued as a Celery task. "
     "With Redis the task runs in a worker process but in local mode, without Redis, it runs inline and the upload call returns when the analysis is done. "
     "The status endpoint reports pending, analyzing, done or failed, and the web application polls it in both modes."),
    ("The metadata agent reads EXIF",
     "The metadata agent reads EXIF data and flags a missing camera make and model, editing or generator software in the tags, missing or inconsistent timestamps and GPS data, and each check gives a score. "
     "A closed form Shapley value shows how much each check moved the score towards authentic or fake, and images with no EXIF at all, such as the PNG files in the datasets, score about 0.45 on this agent."),
    ("The agent combines supporting heuristics",
     "The agent combines supporting heuristics with a trained detector that decides the verdict."),
    ("Error level analysis: the image is re-saved",
     "**Error level analysis:** the image is saved again as JPEG at quality 90 and the amplified difference is saved as a heatmap."),
    ("Frequency analysis: the ratio",
     "**Frequency analysis:** the share of high frequency energy in the Fourier spectrum."),
    ("Grad-CAM [11]: model attention",
     "**Grad-CAM [11]:** the attention of a pretrained deepfake classifier, shown next to the ELA map."),
    ("Trained manipulation detector (this work)",
     "**Trained manipulation detector (this work):** described below, and when it is installed the three heuristics stay in the report as supporting evidence but do not change the score."),
    ("Detector input. The image is re-saved",
     "**The detector input** is made by saving the image again as JPEG at quality 70, 85 and 95 and for each quality we take the absolute difference from the original, turn it to grey scale, amplify it and keep it as one channel. "
     "This gives a three channel error level map at the native resolution of the image (Figure 5.1) and we avoid resizing on purpose because it destroys the faint compression traces that the detector needs."),
    ("Model and training. The network",
     "**The network** is an EfficientNet-B0 [9] with ImageNet weights and a single output, and training uses random 224 × 224 crops of the error level maps with random flips. "
     "We use the AdamW optimiser [49] with learning rate 4×10⁻⁴, a one cycle schedule, weight decay 10⁻⁴, batches of 32, mixed precision and 12 epochs. "
     "At test time up to six crops that cover the image are scored and their outputs are averaged, and the authenticity score is one minus the predicted probability of manipulation."),
    ("Choices made on a development split",
     "**The choices made on a development split** were the input type (one ELA at quality 90 or the three quality map), the backbone (B0 or B3) and the learning rate, and we made them on one development split of CASIA v2.0 which was a validation part of the training data, so the held out test part was not used. "
     "Three quality ELA with B0 gave the best validation accuracy and AUC and we fixed it before any cross-validation, and a six channel input that adds the RGB image to the error maps was clearly worse on one fold so we stopped it and do not use it."),
    ("The provenance agent checks for embedded C2PA",
     "The provenance agent checks for embedded C2PA content credentials [14] and for invisible watermarks written by AI image generators, and a valid manifest moves an image straight to Authentic while a failed manifest or a generator watermark is reported as suspicious and appears in the reasons. "
     "Most images have neither, in which case the agent reports no signal and is left out of the weighted average."),
    ("The engine computes the weighted mean",
     "The engine takes the weighted mean of the agent scores and applies the thresholds, where Authentic is at or above 0.75 and Fake is at or below 0.40 and anything between is Inconclusive, and it also writes a list of reasons. "
     "When the trained detector flags the image the manipulation type is shown as Image Splicing / Tampering, and an Inconclusive image is left for a person to review."),
    ("The analysed file is hashed with SHA-256",
     "The analysed file is hashed with SHA-256 and a standard form of the record (file hash, verdict, score, agent scores and time) is signed with an Ed25519 key [13] and the fingerprint of the public key is stored with it. "
     "The chain of custody lists the upload, analysis, signing and anchoring events, and if a wallet is set the file hash and verdict are written to a smart contract on Polygon Amoy and can be read back for checking. "
     "The evidence PDF holds the identification, the verdict and reasons, the findings of each agent, the explanation exhibits, the chain of custody and the signature."),
    ("A single-page application served by the backend",
     "The web application is a single page served by the backend, where the Analyze page uploads an image and shows the stages and the Report page shows the verdict gauge, the reasons, the findings of each agent, the heatmaps, the Shapley chart, the evidence chain with live checking and the chain of custody. "
     "The History page lists past analyses and the How it works page explains the agents and the weights."),
    ("To compare with [5], a U-Net-style network",
     "To compare with [5] we trained a U-Net [48] style network on the CASIA v2.0 masks, using an EfficientNet-B0 encoder on the RGB image plus the three quality ELA map and a bilinear feature pyramid decoder and a loss that adds binary cross-entropy and Dice. "
     "We tested it on Columbia and Columbia was never used for training or choosing the threshold or early stopping, because the threshold came from a CASIA validation part that keeps sources apart."),
    ("Random 5-fold cross-validation (stratified",
     "**Random 5-fold cross-validation** (stratified, seed 42), which is closest to the base papers."),
    ("Source-disjoint 5-fold cross-validation on CASIA",
     "**Source-disjoint 5-fold cross-validation** on CASIA v2.0, where every tampered image stays in the same fold as the authentic image it was made from, using the source named in the metadata files of the dataset."),
    ("Held-out test of the complete pipeline",
     "**Held out test of the full pipeline** with an 80/20 split that keeps sources together, where a detector trained on the 80% was used by the real agents and the decision engine on the 588 images of the other 20%."),
    ("Columbia: 5-fold cross-validation over",
     "**Columbia:** 5-fold cross-validation over its 363 images with several inputs tried, and all are reported in Chapter 7."),
    ("All metrics come from out-of-fold",
     "All metrics come from out-of-fold or held out predictions, so no image is scored by a model that trained on it."),
    ("A scripted test (scripts/e2e_test.py)",
     "A script (scripts/e2e_test.py) drives a running server through its public API with six images, three authentic and three tampered, and all 19 checks passed. "
     "This includes the tamper check, where changing one byte of a stored evidence file makes the verification endpoint report TAMPERED and restoring the file makes it pass again. "
     "The times in the detail column are for the whole request, with upload, signing and PDF creation included and the model loading during the first image, so they are longer than the 0.24 s spent in the agents and the decision engine."),
    # 6 Demonstration
    ("The screenshots below come from the running application",
     "The screenshots below come from the running application and the images were taken from the held out part of CASIA v2.0 and analysed with the hold-out detector, so the detector had never seen them."),
    ("For a tampered image the report opens with the verdict",
     "For a tampered image the report opens with the verdict, which shows a gauge of the authenticity score, the manipulation type, the reasons and the file hash (Figure 6.3). "
     "The agent breakdown comes next and shows what each agent found, and the image forensics card puts the original, the error level map and the Grad-CAM attention map side by side and gives the probability from the trained detector (Figure 6.4). "
     "The evidence chain checks the file hash and the signature again on every visit and lists the chain of custody (Figure 6.5)."),
    ("Each analysis can be downloaded as an evidence PDF",
     "Each analysis can be downloaded as an evidence PDF with the identification, verdict, findings, heatmaps, chain of custody and signature."),
    # 7 Results
    ("The datasets are CASIA v2.0",
     "The datasets are a subset of CASIA v2.0 and the Columbia set. Our copy of CASIA v2.0 has 1,536 authentic and 1,283 tampered images, all PNG, while the full dataset has 7,491 authentic and 5,123 tampered images, so our results are not on the full set. "
     "Columbia has 183 authentic and 180 spliced images and both come from the Hugging Face collection ductai199x/image-manipulation-dataset-compilation [12] where label 1 means manipulated. "
     "We report accuracy, precision, recall, F1, ROC AUC and the equal error rate (EER), and a confusion matrix is shown for each experiment."),
    ("The two cross-validation protocols give almost the same",
     "The two cross-validation protocols give almost the same accuracy, 95.53% and 95.32%, so keeping each tampered image with its source did not change the result much, although this only controls for the source named in the dataset metadata and not for every near duplicate. "
     "The fold accuracies were 95.9, 95.4, 96.8, 94.2 and 95.4 percent for the random split and 94.0, 96.3, 95.4, 95.9 and 95.0 percent when sources were kept together."),
    ("The real agents and decision engine were run on the 588",
     lambda N: f"The real agents and the decision engine ran on the {N['n']} held out images (301 authentic and 287 tampered) and the engine gave a verdict on {N['cov']} of them and was right on {N['acc_dec']} of those, while the rest went to review. "
               f"If Inconclusive counts as a miss the strict accuracy is {N['strict']}, and if the engine had to choose using the 0.5 mark of its score it would reach {N['forced']} (AUC {N['forced_auc']})."),
    ("Authentic images were called Fake in",
     lambda N: f"Authentic images were called Fake in {N['fp']} of cases and tampered images were called Authentic in {N['fn']}, and most of the cost of the Inconclusive band falls on authentic images because the metadata agent gives a PNG with no EXIF about 0.45 which pulls the combined score towards the middle."),
    ("Columbia consists of uncompressed photographs",
     lambda N: "Columbia has uncompressed photographs, so error level analysis which depends on JPEG history has little to work with, and 363 images are also few for training a network on whole images. "
               "We tried three variants and all are listed above, and the whole image variants are much less stable than on CASIA since their folds differ by more than ten points. "
               "The patch based variant cuts the image into 128 pixel patches and labels them using the ground truth masks and scores an image by the mean of its top 5% patch probabilities and takes the decision threshold from the other folds. "
               "Columbia photographs share scenes, so the last row repeats the test with every scene kept inside one fold and it is the stricter figure. "
               f"The accuracy column is the mean of the five folds, while the abstract gives the accuracy pooled over all 363 images, which is {N['cpg']} for the last row and the same as the mean for the other rows."),
    ("The localiser finds the tampered region well",
     lambda N: f"The localiser finds the tampered region well on images like its training data (pooled F1 {N['loc_a']}) but does not carry over to Columbia (pooled F1 {N['loc_c']} and {N['loc_best']} at the best possible threshold), so localisation across datasets is a limit of this work and the verdict does not use it."),
    ("Only the base-paper results that the detector exceeds",
     "Only the base paper results that our detector exceeds are listed, using a comparable metric on the same dataset, and the protocols differ in splits and subsets and training data since some papers use the full CASIA v2.0 and we use a subset of it, so the table gives context and is not a ranking. "
     "The full comparison, including results we do not reach, is in the file docs/evaluation/EVALUATION.md in the repository."),
    ("The ELA-based detector works well on CASIA",
     "The ELA based detector works well on CASIA v2.0 where most images come from JPEG files but poorly on uncompressed Columbia images, and the patch based detector on noise residuals fixes this on Columbia but it is a separate model, "
     "so the deployed application uses the CASIA detector and a real system will meet both kinds of image."),
    ("Columbia has only 363 images and its photographs share scenes",
     "Columbia has only 363 images and its photographs share scenes, and keeping each scene in one fold lowers accuracy only a little but with so few images the spread between folds is still several points. "
     "The threshold of the patch based detector comes from the other folds' out-of-fold scores and those scores come from models that saw the test fold, so the AUC which does not depend on a threshold is the safer figure."),
    ("CASIA v2.0 is a benchmark with known quirks",
     "CASIA v2.0 has known quirks because tampered images are made from authentic images in the same set, so even the split that keeps sources together is only partly strict, and the held out test uses the same family of data and says little about unrelated images."),
    ("The Inconclusive band costs coverage",
     "The Inconclusive band costs coverage since about one image in ten goes to review, and this is the price for keeping wrong verdicts at about 3% for authentic images and about 1% for tampered images."),
    ("The localiser does not transfer across datasets",
     "The localiser does not carry over to other datasets, so heatmaps are only supporting evidence and the verdict does not depend on them."),
    ("All detector figures are for splicing-style tampering",
     "All figures are for splicing type tampering in CASIA and Columbia and fully AI generated images and heavy recompression and screenshots were not tested."),
    # 8 Conclusion
    ("TrustSphere AI shows that image forensics",
     "TrustSphere AI shows that image forensics and evidence integrity can be built as one system, where a multi-agent pipeline analyses an uploaded image and a decision engine returns Authentic, Fake or Inconclusive with its reasons and every result is hashed and signed and stored with a chain of custody and exported as an evidence PDF. "
     "A web application and a REST API sit on top."),
    ("The trained detector reaches",
     lambda N: f"The trained detector reaches {N['cr']}% accuracy on CASIA v2.0 with random 5-fold cross-validation and {N['cg']}% when tampered images stay with their sources, and on {N['n']} held out images it reaches {N['ho']} while the full pipeline gives a verdict on about {N['cov0']} of them with {N['acc_dec']} accuracy. "
               "These results are higher than those the base papers in Section 7.6 report for CASIA v2.0 under the protocols stated, but the work has limits too since a whole image detector is weak on uncompressed Columbia images and a patch based one reaches about 97% on a very small dataset and a localiser trained on CASIA does not carry over to Columbia."),
    ("Merge the CASIA and Columbia detectors",
     "Merge the CASIA and Columbia detectors into one model that handles compressed and uncompressed images and test it on larger uncompressed sets."),
    ("Evaluate on JPEG-compressed web images",
     "Test on JPEG compressed web images and other benchmarks to measure transfer and add a warning for images that look unlike the training data."),
    ("Improve localisation across datasets",
     "Improve localisation across datasets so the heatmap can support the verdict."),
    ("Re-balance the metadata agent",
     "Rebalance the metadata agent so images without EXIF are not pushed to Inconclusive and tune the verdict thresholds on held out data."),
    ("Host the application and add user accounts",
     "Host the application and add user accounts and access control for case management."),
]
