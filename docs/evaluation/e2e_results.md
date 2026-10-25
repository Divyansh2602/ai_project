# End-to-end test results

Server: `http://127.0.0.1:8001`. 19 of 19 checks passed.

| check | result | detail |
|---|---|---|
| GET /health | pass |  |
| GET /app/ serves the web app | pass |  |
| GET /app/app.js | pass |  |
| GET /docs (OpenAPI) | pass |  |
| analyse Au_ani_30064.jpg.png | pass | verdict Authentic score 0.780, 71.9 s, pdf 290 KB |
| analyse Au_ani_30509.jpg.png | pass | verdict Authentic score 0.780, 9.8 s, pdf 244 KB |
| analyse Au_ani_30704.jpg.png | pass | verdict Authentic score 0.780, 6.7 s, pdf 318 KB |
| analyse Tp_D_CRN_M_N_ani10105_ani00100_100 | pass | verdict Fake score 0.368, 7.0 s, pdf 265 KB |
| analyse Tp_D_CRN_M_N_art10112_cha00086_116 | pass | verdict Fake score 0.183, 8.1 s, pdf 335 KB |
| analyse Tp_D_NRN_S_N_art00051_art00010_010 | pass | verdict Fake score 0.180, 8.8 s, pdf 243 KB |
| history lists every analysis | pass | 6 stored |
| reject text/plain | pass | HTTP 415 |
| reject audio/wav | pass | HTTP 415 |
| reject application/pdf | pass | HTTP 415 |
| reject video/mp4 | pass | HTTP 415 |
| unknown report id -> 404 | pass |  |
| unknown verify id -> 404 | pass |  |
| altering the stored file is detected | pass | integrity TAMPERED |
| restoring the file verifies again | pass | integrity intact |
