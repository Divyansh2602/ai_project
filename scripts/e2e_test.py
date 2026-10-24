"""End-to-end functional test of a RUNNING TrustSphere server (image-only).

    python scripts/e2e_test.py --images <folder with .png/.jpg test images> [--base http://127.0.0.1:8000]

Checks: health and web pages, upload of authentic and tampered images, analysis status, report, evidence PDF, verification (hash, signature),
history, rejection of unsupported types (text, audio, PDF, video), unknown ids, and tamper evidence (changing a stored evidence file must make
verification report TAMPERED). Writes docs/evaluation/e2e_results.md.
"""
import argparse
import hashlib
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
rows = []


def check(name, ok, detail=""):
    rows.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--evidence-dir", default=str(ROOT / "backend" / "uploads"))
    a = ap.parse_args()
    B = a.base.rstrip("/")
    s = requests.Session()
    imgs = sorted(p for p in Path(a.images).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))

    check("GET /health", s.get(B + "/health", timeout=10).json() == {"status": "ok"})
    check("GET /app/ serves the web app", s.get(B + "/app/", timeout=10).status_code == 200)
    check("GET /app/app.js", s.get(B + "/app/app.js", timeout=10).status_code == 200)
    check("GET /docs (OpenAPI)", s.get(B + "/docs", timeout=10).status_code == 200)

    ids = []
    for p in imgs:
        t0 = time.time()
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        up = s.post(B + "/api/upload", files={"file": (p.name, p.read_bytes(), mime)}, timeout=300)
        if up.status_code != 200:
            check(f"upload {p.name[:34]}", False, f"HTTP {up.status_code}")
            continue
        fid = up.json()["file_id"]
        st = "pending"
        for _ in range(150):
            st = s.get(f"{B}/api/status/{fid}", timeout=30).json()["status"]
            if st in ("done", "failed"):
                break
            time.sleep(1)
        rep = s.get(f"{B}/api/report/{fid}", timeout=60).json() if st == "done" else {}
        v = rep.get("verdict", {})
        agents = [x["agent_name"] for x in rep.get("agent_results", [])]
        pdf = s.get(f"{B}/api/report/{fid}/pdf", timeout=120)
        ver = s.get(f"{B}/api/verify/{fid}", timeout=60).json()
        good = (st == "done" and sorted(agents) == ["image_forensics", "metadata", "security"] and pdf.status_code == 200
                and pdf.content[:4] == b"%PDF" and ver["verified"] and ver["file_integrity"]["status"] == "intact"
                and ver["record_signature"]["status"] == "valid")
        check(f"analyse {p.name[:34]}", good, f"verdict {v.get('label')} score {v.get('overall_score', 0):.3f}, {time.time() - t0:.1f} s, pdf {len(pdf.content) // 1024} KB")
        ids.append((fid, p))

    hist = s.get(B + "/api/evidence?limit=50", timeout=30).json()
    check("history lists every analysis", {i for i, _ in ids} <= {h["file_id"] for h in hist}, f"{len(hist)} stored")

    for name, mime in (("note.txt", "text/plain"), ("clip.wav", "audio/wav"), ("doc.pdf", "application/pdf"), ("clip.mp4", "video/mp4")):
        r = s.post(B + "/api/upload", files={"file": (name, b"data", mime)}, timeout=30)
        check(f"reject {mime}", r.status_code == 415, f"HTTP {r.status_code}")
    check("unknown report id -> 404", s.get(B + "/api/report/00000000-0000-0000-0000-000000000000", timeout=30).status_code == 404)
    check("unknown verify id -> 404", s.get(B + "/api/verify/00000000-0000-0000-0000-000000000000", timeout=30).status_code == 404)

    if ids:
        fid, p = ids[0]
        ev = next(iter(Path(a.evidence_dir).glob(hashlib.sha256(p.read_bytes()).hexdigest() + "*")), None)
        if ev is None:
            check("tamper evidence", False, "stored evidence file not found")
        else:
            original = ev.read_bytes()
            ev.write_bytes(original + b"\x00")
            try:
                ver = s.get(f"{B}/api/verify/{fid}", timeout=60).json()
                check("altering the stored file is detected", ver["file_integrity"]["status"] == "TAMPERED" and not ver["verified"], f"integrity {ver['file_integrity']['status']}")
            finally:
                ev.write_bytes(original)
            ver = s.get(f"{B}/api/verify/{fid}", timeout=60).json()
            check("restoring the file verifies again", ver["verified"], f"integrity {ver['file_integrity']['status']}")

    n_ok = sum(1 for _, ok, _ in rows if ok)
    lines = ["# End-to-end test results", "", f"Server: `{B}`. {n_ok} of {len(rows)} checks passed.", "", "| check | result | detail |", "|---|---|---|"]
    lines += [f"| {n} | {'pass' if ok else '**FAIL**'} | {d} |" for n, ok, d in rows]
    (ROOT / "docs" / "evaluation" / "e2e_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{n_ok} of {len(rows)} passed")
    raise SystemExit(0 if n_ok == len(rows) else 1)


if __name__ == "__main__":
    main()
