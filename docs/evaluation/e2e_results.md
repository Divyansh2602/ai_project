# End-to-end test results

Server: `http://127.0.0.1:8000`. 19 of 19 checks passed.

| check | result | detail |
|---|---|---|
| GET /health | pass |  |
| GET /app/ serves the web app | pass |  |
| GET /app/app.js | pass |  |
| GET /docs (OpenAPI) | pass |  |
| analyse Au_ani_20070.jpg.png | pass | verdict Authentic score 0.763, 21.0 s, pdf 312 KB |
| analyse Au_arc_20035.jpg.png | pass | verdict Inconclusive score 0.735, 1.1 s, pdf 737 KB |
| analyse Au_arc_30003.jpg.png | pass | verdict Authentic score 0.780, 0.6 s, pdf 279 KB |
| analyse Tp_D_NNN_S_N_ani10191_ani10200_124 | pass | verdict Fake score 0.180, 1.2 s, pdf 494 KB |
| analyse Tp_D_NRN_S_B_ind00007_cha00040_004 | pass | verdict Fake score 0.282, 0.6 s, pdf 260 KB |
| analyse Tp_D_NRN_S_N_ani00060_ani00059_111 | pass | verdict Fake score 0.185, 0.7 s, pdf 376 KB |
| history lists every analysis | pass | 6 stored |
| reject text/plain | pass | HTTP 415 |
| reject audio/wav | pass | HTTP 415 |
| reject application/pdf | pass | HTTP 415 |
| reject video/mp4 | pass | HTTP 415 |
| unknown report id -> 404 | pass |  |
| unknown verify id -> 404 | pass |  |
| altering the stored file is detected | pass | integrity TAMPERED |
| restoring the file verifies again | pass | integrity intact |
