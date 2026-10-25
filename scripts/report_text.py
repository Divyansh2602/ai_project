"""Plain wording for the project report.

build_report.py looks every body paragraph and bullet up here: if the start of the generated text matches a key, the text below is used instead.
Numbers are filled from the saved metrics (the dict N), never typed in by hand.
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
    "We thank Vellore Institute of Technology (VIT) for giving us the chance and the resources to carry out this project. The facilities and support at VIT helped us build and test our ideas.",
    "We sincerely thank Dr. Jaisankar N, Dean of the School of Computer Science and Engineering (SCOPE), for the support and encouragement given to the students of the school. It motivated us to do our best work.",
    "We thank Dr. Rajeshkannan R, Head of the Department, for guidance and support during this project. The advice and feedback we received helped us shape the work and solve problems along the way.",
    "We are very thankful to our project guide, Manikandan G, Assistant Professor Sr. Grade 2, for regular guidance and useful feedback. The time given in our reviews helped us improve our methods and finish this work.",
    "Thank you all for your support.",
]


def abstract(N):
    return [
        "Photographs are used as evidence in news, insurance, banking and courts. Editing tools make it easy to paste part of one image into another. "
        "Deciding whether an image was changed is one problem. Proving later that the decision was not altered is another. "
        "This project builds TrustSphere AI, a system for still images that handles both. Three agents look at each uploaded image. "
        "A metadata agent reads the EXIF data. An image forensics agent studies the pixels. A provenance agent checks content credentials and invisible watermarks. "
        "A decision engine combines their scores into a verdict of Authentic, Fake or Inconclusive. "
        "Each result is hashed with SHA-256, signed with Ed25519, stored with a chain of custody, anchored on a test blockchain if a wallet is set, and saved as an evidence PDF. "
        "A web application shows the whole process.",
        "The image forensics agent uses a detector we trained. It is an EfficientNet-B0 network that reads error level analysis maps made at three JPEG qualities, using crops at the original resolution. "
        f"We trained and tested it on a subset of CASIA v2.0 (1,536 authentic and 1,283 tampered images) and on Columbia (183 authentic and 180 spliced images). "
        f"With 5-fold cross-validation on CASIA v2.0 the accuracy is {N['cr']}% with a random split and {N['cg']}% when each tampered image stays in the same fold as its source. "
        f"On {N['n']} images that were never used in training it reaches {N['ho']} and the full pipeline gives a verdict on {N['cov']} of them with {N['acc_dec']} accuracy. The rest go to a person. "
        f"Columbia is harder because its photos are uncompressed. A whole image detector reaches only {N['ce']}%, while a patch based detector on noise residuals reaches {N['cp']} with a random split "
        f"and {N['cpg']} when every scene stays in one fold. A model that outlines the tampered area, trained on CASIA, does not work well on Columbia (pixel F1 {N['loc_c']}). "
        "We compare the results with the five base papers and state this weakness.",
    ]


# (start of the generated text without ** marks, replacement)
OVERRIDES = [
    # 1 Introduction
    ("Photographs are accepted as evidence in newsrooms",
     "Photographs are accepted as evidence in newsrooms, insurance claims, banks and courts. The same tools that fix a holiday photo can move an object into a scene, remove a person or paste a face onto another body. "
     "The result often looks real to the eye. Image forensics asks whether an image is authentic. Passive methods use only the image. "
     "They look for traces that editing leaves behind, such as different noise, colour patterns or JPEG compression history between the pasted part and the rest of the picture."),
    ("A second question is just as important",
     "A second question matters just as much. After an image is analysed, can anyone prove which file was checked, what the verdict was and that the record was not changed? "
     "A detector that only prints a score cannot answer this. So we built the analysis and the evidence record as one system. "
     "Each run gives a verdict, the evidence behind it such as scores, heatmaps and reasons, and a record that anyone can check with cryptography."),
    ("Published splicing detectors report accuracies",
     "Published splicing detectors report accuracies above 90% on CASIA v2.0 and Columbia, but most are research code. They give a label for one dataset and stop. "
     "An analyst needs an application that takes any image and explains its answer."),
    ("A wrong automatic verdict can accuse",
     "A wrong automatic verdict can blame an innocent photographer or clear a fake. The system should be able to say Inconclusive and pass the image to a person."),
    ("Evidence has to survive scrutiny",
     "Evidence must hold up when it is questioned. A SHA-256 hash of the exact file, a digital signature on the record and an optional public timestamp let a third party check that nothing changed after the analysis."),
    ("No single signal can be trusted alone",
     "No single signal can be trusted alone. Metadata is easy to remove, recompression hides ELA traces and most images carry no provenance data. Several agents cover for each other."),
    ("TrustSphere AI analyses still images only",
     "TrustSphere AI analyses still images only. Earlier versions of the project also handled audio and documents. We removed both, and none of their code, data or results appear in this report."),
    ("Included: image upload",
     "**Included:** image upload, a metadata agent, an image forensics agent with a trained detector, a provenance agent, a decision engine, SHA-256 hashing, Ed25519 signing, a chain of custody, optional blockchain anchoring, an evidence PDF, a REST API and a web application."),
    ("Experiments: image-level detection",
     "**Experiments:** detection accuracy by cross-validation, a test of the full pipeline on held out images and a localisation experiment."),
    ("Not included: video",
     "**Not included:** video, audio, document forensics, training on fully AI generated images and any legal judgement. The score is meant to support a decision, not replace it."),
    # 2 Literature review
    ("Image forgery falls into three common kinds",
     "Image forgery has three common kinds. In splicing, a part of one image is pasted into another. In copy-move, a part is copied within the same image. In removal, an object is erased and the gap is filled [5]. "
     "Classic detectors look for mismatches in noise, in colour filter patterns, in lighting and in double JPEG compression, because a pasted part keeps the statistics of its source image [5]. "
     "Error level analysis (ELA) was described for forensic use by Krawetz [10]. It saves an image again as JPEG at a known quality and shows the difference, so parts with a different compression history stand out."),
    ("Deep learning replaced hand-crafted features",
     "Deep learning has replaced hand made features in most recent work. Salloum et al. [6] trained a fully convolutional network on CASIA v2.0 to predict both the spliced region and its boundary. "
     "They tested it on CASIA v1.0, Columbia and other sets. Training on CASIA and testing elsewhere was later used by [5]."),
    ("Early passive methods rely on physical traces",
     "Early passive methods use traces left by the camera and the editing steps. Scaling or rotating leaves repeating patterns between neighbouring pixels [15]. "
     "Camera colour interpolation leaves patterns that a pasted part tends to lack [16]. Sensor noise works like a fingerprint of the camera, and a region without it may be tampered [17]. "
     "Mahdian and Saic look for regions with a different noise level [18]. For JPEG images, JPEG ghosts show a region first saved at another quality [19], and Bianchi and Piva estimate the chance of tampering for each 8 × 8 block [20]. "
     "Copy-move forgery was first found by matching blocks [21]. SIFT keypoints can also give the transformation of the copied region [22], and Christlein et al. compared fifteen feature sets in one pipeline [23]. "
     "Splicebuster models noise residuals and splits the image into real and spliced parts without any forged training examples [24]. "
     "The filters of the rich models by Fridrich and Kodovský were made for steganalysis [25]. We use them as the SRM input for Columbia."),
    ("Deep networks learn such traces from data",
     "Deep networks learn these traces from data. Bayar and Stamm add a constrained first layer that suppresses image content and learns features for manipulation detection [26]. "
     "Zhou et al. use an RGB stream and a noise stream in a Faster R-CNN [27]. Huh et al. train only on real photos and use their EXIF data to learn whether an image is self consistent, meaning that it could come from one imaging pipeline. They then use this to find splices without ever seeing forged examples [28]. "
     "BusterNet separates the source and target regions of copy-move forgery [29]. ManTra-Net learns many manipulation types and treats localisation as finding anomalies [30]. "
     "RRU-Net adds residual feedback to a U-Net [31]. PSCC-Net predicts masks step by step at several scales [32]. MVSS-Net learns from the noise view and from boundary artifacts, and is supervised at several scales [33]. "
     "CAT-Net learns from JPEG DCT coefficients and pixels [34]. ObjectFormer uses RGB and high frequency features in a transformer [35]. TruFor adds a learned noise fingerprint and a reliability map [36]. "
     "Most of these papers are judged on how well they locate the tampered pixels. Our detector answers the image level question of authentic or tampered. The base papers [1] to [4] answer the same question."),
    ("Surveys of the field are given in",
     "Surveys are given in [37] to [40]. Verdoliva covers media forensics and deepfakes [37]. Qureshi and Deriche list pixel based blind methods [38]. Stamm et al. describe the first ten years of information forensics [39]. "
     "Warif et al. review copy-move detection [40]. Muhammad et al. tell authentic from tampered images using a steerable pyramid transform and local binary patterns on the colour channels [41]. "
     "Besides CASIA [7] and the Columbia splicing set [8], other datasets in this field are the Columbia set of authentic and spliced blocks [42], CoMoFoD [43], COVERAGE [44] and the Dresden image database [45]. "
     "Our building blocks are standard. Residual networks [46] and vision transformers [47] are common alternatives to our EfficientNet backbone [9]. The localiser follows the U-Net layout [48] and training uses AdamW [49]. "
     "For evidence, Hasan and Salah used Ethereum smart contracts to track where a media file came from using file hashes [50]. We store a SHA-256 hash of the analysed image in a similar way and add a signature and a chain of custody."),
    ("The five base papers of this project are summarised next",
     "The five base papers of this project are summarised next."),
    ("Ranjan et al. combine a local optimal",
     "Ranjan et al. extract texture maps with the Local Optimal Oriented Pattern (LOOP), refine them with a pretrained ResNet-50 and classify with an SVM. "
     "They test on the Columbia splicing dataset, CASIA v2.0 and a part of the Dresden image database using stratified 5-fold cross-validation. Their average accuracy is 95.20%. "
     "Their review table lists earlier methods that use Columbia, with accuracies between about 91% and 93.4%."),
    ("Ravula and Singh detect and classify",
     "Ravula and Singh detect and classify copy-move forgery using generative adversarial networks, a vision transformer and spectral clustering together. "
     "In their Table 4 they report accuracy of 98.95% on CoMoFoD, 95.2% on MICC-F220 and 94.4% on CASIA v2. Their abstract gives 99.02% accuracy for CoMoFoD."),
    ("Rehman and Jain extract patch descriptors",
     "Rehman and Jain take patch features from a pretrained CNN, fuse them and classify with an SVM. On CASIA v2.0 they report 93.57% accuracy without augmentation and 98.91% with augmentation. "
     "Their Table 3 uses 10-fold cross-validation. For batch size 128 it gives accuracy 98.91%, mean 93.39% and standard deviation 8.75%. For batch size 200 it gives accuracy 93.57%, mean 90.25% and standard deviation 7.98%."),
    ("Deb and Kar propose a CNN-based",
     "Deb and Kar propose a CNN based copy-move method with preprocessing, feature extraction, segmentation and localisation steps. They also study how different the datasets are. "
     "On CASIA v2.0 they report precision 87.31, recall 90.15 and F1 88.33."),
    ("Chen et al. extract features from a frozen",
     "Chen et al. take features from a pretrained EfficientNet-B4 and train XGBoost models at several levels for the splicing mask. A second version also predicts the mask boundary. No backpropagation is needed. "
     "Following [6], they train on CASIA v2.0 and test on CASIA v1.0 and Columbia. They report pixel F1 of 0.5728 (0.6210 with edges) on CASIA v1.0 and 0.6497 (0.6558) on Columbia, with 18.4 million parameters for GIFT."),
    ("Evaluation that may reward memorisation",
     "**Tests that may reward memory.** CASIA v2.0 has tampered images made from authentic images in the same set. A random split can put a tampered image in the test set and its source in the training set. "
     "The base papers report random split or cross-validation accuracy and do not say if sources were kept apart. We report both a random split and a split that keeps sources together."),
    ("Detection without evidence",
     "**Detection without evidence.** The base papers stop at a label or a mask. None of them hashes the file, signs the result or gives a record that a third party can check."),
    ("Prototypes, not applications",
     "**Prototypes instead of applications.** The published methods are scripts for one benchmark. An analyst gets no upload page, no explanation of the verdict and no way to review earlier cases."),
    ("Weak transfer",
     "**Weak transfer.** The protocol of [5] and [6] trains on CASIA v2.0 and tests on Columbia. It gives pixel F1 of about 0.65 at best. Behaviour on a new dataset is still an open problem, and a system should say so."),
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
     "Given a still image of unknown origin, decide whether it is authentic or manipulated and show the evidence for the decision. Say Inconclusive when the evidence is weak. "
     "Keep a record of the analysis that a third party can check without trusting the operator."),
    ("The plan follows the history of the project repository",
     "The plan follows the history of the project repository. The dates are the dates of the work. The training and evaluation work of October 2026 was done in this semester."),
    # 3 Technical specification
    ("FR1. Accept an uploaded image",
     "FR1. Accept an uploaded image (JPEG, PNG, WebP, GIF, BMP or TIFF) up to 100 MB and reject every other file type with HTTP 415."),
    ("FR3. Run the metadata",
     "FR3. Run the metadata, image forensics and provenance agents and store what each agent finds."),
    ("FR4. Fuse the agent scores",
     "FR4. Combine the agent scores into an authenticity score between 0 and 1 and a verdict. Authentic is at or above 0.75, Fake is at or below 0.40 and anything between is Inconclusive."),
    ("FR5. Show the reasoning",
     "FR5. Show the reasons, the heatmaps (error level analysis and Grad-CAM) and how much each metadata field contributed."),
    ("FR6. Sign every record",
     "FR6. Sign every record with Ed25519, keep a chain of custody and, if a wallet is set, anchor the verdict on the Polygon Amoy blockchain."),
    ("FR7. Generate an evidence PDF",
     "FR7. Create an evidence PDF and let anyone check the file hash, the signature and the anchor again."),
    ("FR8. Provide a web application",
     "FR8. Provide a web application and a documented REST API."),
    ("Accuracy and honesty",
     "**Accuracy:** only cross-validated and held out figures are reported, with the protocol stated."),
    ("Performance: analyse one image",
     "**Speed:** analyse one image in seconds on one GPU. On the 588 held out images the whole pipeline took 0.24 s per image on average, about 142 s in total."),
    ("Integrity: any change",
     "**Integrity:** any change to a stored file or record must be detectable."),
    ("Portability: run on one Windows",
     "**Portability:** run on one Windows machine with SQLite and no Redis, and also with PostgreSQL and Redis."),
    ("Security: signing keys",
     "**Security:** signing keys, wallet keys and environment files are never committed to the repository."),
    ("Maintainability: each agent",
     "**Maintainability:** each agent is one module with the same interface, so one agent can be replaced without touching the others."),
    ("Every component is available as open-source",
     "Every part is available as open source software (Python, PyTorch, timm, FastAPI, SQLAlchemy, ReportLab and web3). The detector is small. EfficientNet-B0 has about 4 million parameters, "
     "and we trained and tested it on one laptop GPU with 8 GB of memory. We start from pretrained ImageNet weights, so no large dataset or cluster is needed."),
    ("No paid service was used",
     "No paid service was used. The models and libraries are open source and the datasets are public. The database is SQLite or a free PostgreSQL plan. "
     "Blockchain anchoring uses the Polygon Amoy test network, where gas is free. The only hardware is the development laptop, so the running cost is only electricity."),
    ("The system supports journalists",
     "The system helps journalists, insurers and investigators sort images. The main risk is trusting an automatic verdict too much. "
     "The design reduces this with an Inconclusive band, visible reasons and heatmaps, and a note that scores are not a legal finding. "
     "Images are processed on the operator's own machine and are not sent to anyone else."),
    # 4 Design
    ("The user uploads an image through the web application",
     "The user uploads an image in the web application. The FastAPI backend stores the file, hashes it and runs three agents. Each agent returns a score from 0 (fake) to 1 (authentic) and a list of findings. "
     "The decision engine takes the weighted average of the scores. The weights are 0.30 for image forensics, 0.25 for provenance and 0.20 for metadata. "
     "An agent with no signal is left out instead of being counted as 0.5. The average becomes a verdict. "
     "The record is then signed, saved in the database with a chain of custody, anchored on the blockchain if set up, and made available as JSON and as an evidence PDF."),
    ("Figure 4.2 shows the level-1 data flow",
     "Figure 4.2 shows the level 1 data flow. The original file and its hash go to the evidence store. The forensic agents read the trained model weights. "
     "The signed record goes back to the store and the report goes to the analyst."),
    ("The analyst uploads images, reads verdicts",
     "The analyst uploads images, reads verdicts and heatmaps, downloads the evidence PDF and browses the history. A verifier or auditor does not have to trust the analyst, "
     "because the verdict, the evidence PDF and the integrity check are open to anyone who has the file identifier."),
    ("The data model has four tables",
     "The data model has four tables. Evidence holds the uploaded file, AgentResult has one row per agent, FinalVerdict has one row per analysis and AuditLog holds the signature, anchor and chain of custody. "
     "All agents use the same run(path) interface, so the decision engine treats them the same way."),
    ("Figure 4.6 shows one analysis from upload",
     "Figure 4.6 shows one analysis from upload to report. Report and verification are separate requests, so verification can be repeated at any later time."),
    # 5 Methodology
    ("The upload endpoint accepts only image MIME types",
     "The upload endpoint accepts only image MIME types. The file is saved under its SHA-256 hash, a database row is created and the analysis is queued as a Celery task. "
     "With Redis the task runs in a worker process. In local mode, without Redis, it runs inline and the upload call returns when the analysis is done. "
     "The status endpoint reports pending, analyzing, done or failed, and the web application polls it in both modes."),
    ("The metadata agent reads EXIF",
     "The metadata agent reads EXIF data and flags a missing camera make and model, editing or generator software in the tags, missing or inconsistent timestamps and GPS data. Each check gives a score. "
     "A closed form Shapley value shows how much each check moved the score towards authentic or fake. Images with no EXIF at all, such as the PNG files in the datasets, score about 0.45 on this agent."),
    ("The agent combines supporting heuristics",
     "The agent combines supporting heuristics with a trained detector that decides the verdict."),
    ("Error level analysis: the image is re-saved",
     "**Error level analysis:** the image is saved again as JPEG at quality 90 and the amplified difference is saved as a heatmap."),
    ("Frequency analysis: the ratio",
     "**Frequency analysis:** the share of high frequency energy in the Fourier spectrum."),
    ("Grad-CAM [11]: model attention",
     "**Grad-CAM [11]:** the attention of a pretrained deepfake classifier, shown next to the ELA map."),
    ("Trained manipulation detector (this work)",
     "**Trained manipulation detector (this work):** described below. When it is installed, the three heuristics stay in the report as supporting evidence but do not change the score."),
    ("Detector input. The image is re-saved",
     "**Detector input.** The image is saved again as JPEG at quality 70, 85 and 95. For each quality we take the absolute difference from the original, turn it to grey scale, amplify it and keep it as one channel. "
     "This gives a three channel error level map at the native resolution of the image (Figure 5.1). We avoid resizing on purpose because it destroys the faint compression traces the detector needs."),
    ("Model and training. The network",
     "**Model and training.** The network is an EfficientNet-B0 [9] with ImageNet weights and a single output. Training uses random 224 × 224 crops of the error level maps with random flips. "
     "We use the AdamW optimiser with learning rate 4×10⁻⁴, a one cycle schedule, weight decay 10⁻⁴, batches of 32, mixed precision and 12 epochs. "
     "At test time up to six crops that cover the image are scored and their outputs are averaged. The authenticity score is one minus the predicted probability of manipulation."),
    ("Choices made on a development split",
     "**Choices made on a development split.** We chose the input type (one ELA at quality 90 or the three quality map), the backbone (B0 or B3) and the learning rate on one development split of CASIA v2.0. "
     "This was a validation part of the training data and the held out test part was not used. Three quality ELA with B0 gave the best validation accuracy and AUC, and we fixed it before any cross-validation. "
     "We also tried a six channel input that adds the RGB image to the error maps on one fold. It was clearly worse, so we stopped it and do not use it."),
    ("The provenance agent checks for embedded C2PA",
     "The provenance agent checks for embedded C2PA content credentials [14] and for invisible watermarks written by AI image generators. A valid manifest moves an image straight to Authentic. "
     "A failed manifest or a generator watermark is reported as suspicious and appears in the reasons. Most images have neither. In that case the agent reports no signal and is left out of the weighted average."),
    ("The engine computes the weighted mean",
     "The engine takes the weighted mean of the agent scores and applies the thresholds. Authentic is at or above 0.75, Fake is at or below 0.40 and anything between is Inconclusive. It also writes a list of reasons. "
     "When the trained detector flags the image, the manipulation type is shown as Image Splicing / Tampering. The Inconclusive band is deliberate. It sends borderline images to a person."),
    ("The analysed file is hashed with SHA-256",
     "The analysed file is hashed with SHA-256. A standard form of the record (file hash, verdict, score, agent scores and time) is signed with an Ed25519 key [13] and the fingerprint of the public key is stored with it. "
     "The chain of custody lists the upload, analysis, signing and anchoring events. If a wallet is set, the file hash and verdict are written to a smart contract on Polygon Amoy and can be read back for checking. "
     "The evidence PDF holds the identification, the verdict and reasons, the findings of each agent, the explanation exhibits, the chain of custody and the signature."),
    ("A single-page application served by the backend",
     "The web application is a single page served by the backend. The Analyze page uploads an image and shows the stages. "
     "The Report page shows the verdict gauge, the reasons, the findings of each agent, the heatmaps, the Shapley chart, the evidence chain with live checking and the chain of custody. "
     "The History page lists past analyses. The How it works page explains the agents and the weights."),
    ("To compare with [5], a U-Net-style network",
     "To compare with [5], we trained a U-Net style network on the CASIA v2.0 masks. It uses an EfficientNet-B0 encoder on the RGB image plus the three quality ELA map, a bilinear feature pyramid decoder and a loss that adds binary cross-entropy and Dice. "
     "We tested it on Columbia. Columbia was never used for training, choosing the threshold or early stopping. The threshold came from a CASIA validation part that keeps sources apart."),
    ("Random 5-fold cross-validation (stratified",
     "**Random 5-fold cross-validation** (stratified, seed 42). This is closest to the base papers."),
    ("Source-disjoint 5-fold cross-validation on CASIA",
     "**Source-disjoint 5-fold cross-validation** on CASIA v2.0. Every tampered image stays in the same fold as the authentic image it was made from, using the source named in the metadata files of the dataset."),
    ("Held-out test of the complete pipeline",
     "**Held out test of the full pipeline.** An 80/20 split that keeps sources together. A detector trained on the 80% was used by the real agents and the decision engine on the 588 images of the other 20%."),
    ("Columbia: 5-fold cross-validation over",
     "**Columbia.** 5-fold cross-validation over its 363 images with several inputs tried. All are reported in Chapter 7."),
    ("All metrics come from out-of-fold",
     "All metrics come from out-of-fold or held out predictions, so no image is scored by a model that trained on it."),
    ("A scripted test (scripts/e2e_test.py)",
     "A script (scripts/e2e_test.py) drives a running server through its public API with six images, three authentic and three tampered. All 19 checks passed. "
     "This includes the tamper check. Changing one byte of a stored evidence file makes the verification endpoint report TAMPERED, and restoring the file makes it pass again."),
    # 6 Demonstration
    ("The screenshots below come from the running application",
     "The screenshots below come from the running application. The images were taken from the held out part of CASIA v2.0 and analysed with the hold-out detector, so the detector had never seen them."),
    ("For a tampered image the report opens with the verdict",
     "For a tampered image the report opens with the verdict. It shows a gauge of the authenticity score, the manipulation type, the reasons and the file hash (Figure 6.3). "
     "The agent breakdown comes next and shows what each agent found. The image forensics card puts the original, the error level map and the Grad-CAM attention map side by side and gives the probability from the trained detector (Figure 6.4). "
     "The evidence chain checks the file hash and the signature again on every visit and lists the chain of custody (Figure 6.5)."),
    ("Each analysis can be downloaded as an evidence PDF",
     "Each analysis can be downloaded as an evidence PDF with the identification, verdict, findings, heatmaps, chain of custody and signature."),
    # 7 Results
    ("The datasets are CASIA v2.0",
     "The datasets are a subset of CASIA v2.0 and the Columbia set. Our copy of CASIA v2.0 has 1,536 authentic and 1,283 tampered images, all PNG. The full dataset has 7,491 authentic and 5,123 tampered images, so our results are not on the full set. "
     "Columbia has 183 authentic and 180 spliced images. Both come from the Hugging Face collection ductai199x/image-manipulation-dataset-compilation [12]. Label 1 means manipulated. "
     "We report accuracy, precision, recall, F1, ROC AUC and the equal error rate (EER). A confusion matrix is shown for each experiment."),
    ("The two cross-validation protocols give almost the same",
     "The two cross-validation protocols give almost the same accuracy, 95.53% and 95.32%. Keeping each tampered image with its source did not change the result much. "
     "This only controls for the source named in the dataset metadata and not for every near duplicate. "
     "The fold accuracies were 95.9, 95.4, 96.8, 94.2 and 95.4 percent for the random split, and 94.0, 96.3, 95.4, 95.9 and 95.0 percent when sources were kept together."),
    ("The real agents and decision engine were run on the 588",
     lambda N: f"The real agents and the decision engine ran on the {N['n']} held out images (301 authentic and 287 tampered). The engine gave a verdict on {N['cov']} of them and was right on {N['acc_dec']} of those. "
               f"The rest went to review. If Inconclusive counts as a miss, the strict accuracy is {N['strict']}. If the engine had to choose using the 0.5 mark of its score, it would reach {N['forced']} (AUC {N['forced_auc']})."),
    ("Authentic images were called Fake in",
     lambda N: f"Authentic images were called Fake in {N['fp']} of cases and tampered images were called Authentic in {N['fn']}. Most of the cost of the Inconclusive band falls on authentic images. "
               "The metadata agent gives a PNG with no EXIF about 0.45, which pulls the combined score towards the middle."),
    ("Columbia consists of uncompressed photographs",
     "Columbia has uncompressed photographs, so error level analysis, which depends on JPEG history, has little to work with. Also, 363 images are few for training a network on whole images. "
     "We tried three variants and all are listed above. The whole image variants are much less stable than on CASIA, and their folds differ by more than ten points. "
     "The patch based variant cuts the image into 128 pixel patches and labels them using the ground truth masks. It scores an image by the mean of its top 5% patch probabilities and takes the decision threshold from the other folds. "
     "Columbia photographs share scenes, so the last row repeats the test with every scene kept inside one fold. It is the stricter figure."),
    ("The localiser finds the tampered region well",
     lambda N: f"The localiser finds the tampered region well on images like its training data (pooled F1 {N['loc_a']}) but does not carry over to Columbia (pooled F1 {N['loc_c']}, and {N['loc_best']} at the best possible threshold). "
               "Localisation across datasets is a limit of this work. The verdict does not use it."),
    ("Only the base-paper results that the detector exceeds",
     "Only the base paper results that our detector exceeds are listed, using a comparable metric on the same dataset. The protocols differ in splits, subsets and training data. For example, some papers use the full CASIA v2.0 and we use a subset of it. So the table gives context and is not a ranking. "
     "The full comparison, including results we do not reach, is in the file docs/evaluation/EVALUATION.md in the repository."),
    ("The ELA-based detector works well on CASIA",
     "The ELA based detector works well on CASIA v2.0, where most images come from JPEG files, and poorly on uncompressed Columbia images. The patch based detector on noise residuals fixes this on Columbia but it is a separate model. "
     "The deployed application uses the CASIA detector, and a real system will meet both kinds of image."),
    ("Columbia has only 363 images and its photographs share scenes",
     "Columbia has only 363 images and its photographs share scenes. Keeping each scene in one fold lowers accuracy only a little, but with so few images the spread between folds is still several points. "
     "The threshold of the patch based detector comes from the other folds' out-of-fold scores, and those scores come from models that saw the test fold. The AUC does not depend on a threshold, so it is the safer figure."),
    ("CASIA v2.0 is a benchmark with known quirks",
     "CASIA v2.0 has known quirks. Tampered images are made from authentic images in the same set, so even the split that keeps sources together is only partly strict. "
     "The held out test uses the same family of data and says little about unrelated images."),
    ("The Inconclusive band costs coverage",
     "The Inconclusive band costs coverage, since about one image in ten goes to review. This is the price for keeping wrong verdicts at about 3% for authentic images and about 1% for tampered images."),
    ("The localiser does not transfer across datasets",
     "The localiser does not carry over to other datasets, so heatmaps are only supporting evidence. The verdict does not depend on them."),
    ("All detector figures are for splicing-style tampering",
     "All figures are for splicing type tampering in CASIA and Columbia. Fully AI generated images, heavy recompression and screenshots were not tested."),
    # 8 Conclusion
    ("TrustSphere AI shows that image forensics",
     "TrustSphere AI shows that image forensics and evidence integrity can be built as one system. A multi-agent pipeline analyses an uploaded image and a decision engine returns Authentic, Fake or Inconclusive with its reasons. "
     "Every result is hashed, signed, stored with a chain of custody and exported as an evidence PDF. A web application and a REST API sit on top."),
    ("The trained detector reaches",
     lambda N: f"The trained detector reaches {N['cr']}% accuracy on CASIA v2.0 with random 5-fold cross-validation and {N['cg']}% when tampered images stay with their sources. "
               f"On {N['n']} held out images it reaches {N['ho']}, and the full pipeline gives a verdict on about {N['cov0']} of them with {N['acc_dec']} accuracy. "
               "These results are higher than those the base papers in Section 7.6 report for CASIA v2.0 under the protocols stated. The work has limits too. "
               "A whole image detector is weak on uncompressed Columbia images. A patch based one reaches about 97% on a very small dataset. A localiser trained on CASIA does not carry over to Columbia."),
    ("Merge the CASIA and Columbia detectors",
     "Merge the CASIA and Columbia detectors into one model that handles compressed and uncompressed images, and test it on larger uncompressed sets."),
    ("Evaluate on JPEG-compressed web images",
     "Test on JPEG compressed web images and other benchmarks to measure transfer, and add a warning for images that look unlike the training data."),
    ("Improve localisation across datasets",
     "Improve localisation across datasets so the heatmap can support the verdict."),
    ("Re-balance the metadata agent",
     "Rebalance the metadata agent so images without EXIF are not pushed to Inconclusive, and tune the verdict thresholds on held out data."),
    ("Host the application and add user accounts",
     "Host the application and add user accounts and access control for case management."),
]
