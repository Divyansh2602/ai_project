# Results of the end-to-end run

Every file below was uploaded to a running server, analyzed by the multi-agent pipeline, and its report, evidence PDF and verification were fetched. Reports (JSON) and evidence PDFs are in [docs/outputs/reports](outputs/reports).

| file | type | expected | verdict | authenticity | manipulation type | agents that ran | seconds |
|---|---|---|---|---|---|---|---|
| 10_photo_matched_SPLICED.jpg | image | Fake | **Inconclusive** | 0.492 | GAN / AI-Generated Image | metadata, image_forensics, security | 0.8 |
| 1_receipt_AUTHENTIC.png | image | Authentic | **Inconclusive** | 0.459 | GAN / AI-Generated Image | metadata, image_forensics, security | 0.3 |
| 2_receipt_TAMPERED.png | image | Fake | **Inconclusive** | 0.510 | Spliced / Copy-Move Forgery | metadata, image_forensics, security | 0.3 |
| 5_document_AUTHENTIC.pdf | document | Authentic | **Inconclusive** | 0.450 |  | metadata, security | 0.2 |
| 6_document_TAMPERED.pdf | document | Fake | **Inconclusive** | 0.450 |  | metadata, security | 0.2 |
| 7_audio_AUTHENTIC.wav | audio | Authentic | **Inconclusive** | 0.632 | Voice Clone / Synthetic Speech | metadata, audio_forensics, security | 0.3 |
| 8_audio_FAKE.wav | audio | Fake | **Fake** | 0.289 | Voice Clone / Synthetic Speech | metadata, audio_forensics, security | 0.3 |
| 9_photo_matched_AUTHENTIC.jpg | image | Authentic | **Inconclusive** | 0.517 | Spliced / Copy-Move Forgery | metadata, image_forensics, security | 0.6 |

## Reading these results honestly

* 8 files ran through upload, analysis, report, evidence PDF and verification with no errors. Unsupported types (text, video) are rejected with HTTP 415.
* The system made a call on 1 of 8 files and was right there (`8_audio_FAKE.wav` is Fake). The other 7 came out **Inconclusive** (score between 0.40 and 0.75), including the authentic files and the tampered ones. Nothing authentic was called Fake and nothing tampered was called Authentic, but most files are sent to human review rather than decided.
* **Documents** get only the metadata and provenance agents (there is no document-content agent), so a PDF always lands near 0.45 Inconclusive.
* **Images**: the image agent combines error-level analysis, a frequency check and a deep classifier. On these files it does not separate authentic from spliced or tampered images; the manipulation label (for example "GAN / AI-Generated Image") should be read as a weak hint, not a finding.
* **Audio**: the audio agent separates the two clips clearly (authentic clip 0.81, fake clip 0.13; the deep synthetic-speech classifier gives 1.00 and 0.01). The authentic clip still ends at 0.63 overall because the metadata agent contributes a low score (0.45: audio files carry no camera or timestamp tags), which pulls the fused score into the Inconclusive band.

The input files are demo files and are not included in this repository.
