"""Clean, publication-quality diagrams for the project report.

Graphviz (vector layout, orthogonal edges) for the architecture, methodology, data-flow, use-case and class diagrams; a hand-built SVG for the
sequence diagram. Everything is written as SVG and rendered to a 300 dpi PNG.

    python scripts/make_report_diagrams.py
"""
import os
import subprocess
from pathlib import Path

GV = Path(r"C:\Program Files\Graphviz\bin")
os.environ["PATH"] = str(GV) + os.pathsep + os.environ["PATH"]
OUT = Path(__file__).resolve().parent.parent / "docs" / "report" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

FONT = "Arial"
NAVY, BLUE, TEAL, AMBER, GREY, INK = "#0b3b6f", "#1560bd", "#0e9f8e", "#b7791f", "#5b6b80", "#0f1b2d"
F_NAVY, F_BLUE, F_TEAL, F_AMBER, F_GREY = "#e4edf8", "#e2f0ff", "#def5f0", "#fdf1d6", "#f3f6fa"

HEAD = f'''digraph G {{
  graph [fontname="{FONT}", fontsize=15, labelloc=t, pad=0.3, nodesep=0.35, ranksep=0.55, splines=ortho, bgcolor=white, dpi=300];
  node  [fontname="{FONT}", fontsize=12, shape=box, style="rounded,filled", fillcolor="{F_GREY}", color="{NAVY}", penwidth=1.4, margin="0.18,0.10", fontcolor="{INK}"];
  edge  [fontname="{FONT}", fontsize=10, color="{GREY}", penwidth=1.3, arrowsize=0.8, fontcolor="{GREY}"];
'''


def render(name, dot, png_only=False):
    src = OUT / f"{name}.dot"
    src.write_text(dot + "\n}\n", encoding="utf-8")
    for fmt in ("svg", "png"):
        subprocess.run([str(GV / "dot.exe"), f"-T{fmt}", str(src), "-o", str(OUT / f"{name}.{fmt}")], check=True)
    src.unlink()
    print("wrote", name)


# 1. architecture ───────────────────────────────────────────────────────────────────────
render("fig_architecture", HEAD + f'''
  label="System architecture of TrustSphere AI";  rankdir=LR; compound=true;
  user  [label="Analyst\\n(web browser or\\nChrome extension)", fillcolor="{F_AMBER}", color="{AMBER}"];
  subgraph cluster_api {{ label="FastAPI backend"; style="rounded,filled"; fillcolor="#f4faf6"; color="#1a8f4c"; fontcolor="#1a8f4c"; labeljust=l;
    api [label="REST API\\nupload  |  status  |  report\\nverify  |  history  |  evidence PDF", fillcolor="white", color="#1a8f4c"]; }}
  subgraph cluster_ag {{ label="Forensic agents"; style="rounded,filled"; fillcolor="#f7f9fc"; color="{NAVY}"; fontcolor="{NAVY}"; labeljust=l;
    meta [label="Metadata agent\\nEXIF, software tags,\\ntimestamps, GPS", fillcolor="white"];
    img  [label="Image forensics agent\\ntrained detector (EfficientNet-B0\\non multi-quality ELA maps),\\nELA, FFT, Grad-CAM", fillcolor="{F_BLUE}", color="{BLUE}", penwidth=2];
    prov [label="Provenance agent\\nC2PA credentials,\\ninvisible watermark", fillcolor="white"]; }}
  dec   [label="Decision engine\\nweighted fusion\\nAuthentic | Fake | Inconclusive", fillcolor="{F_AMBER}", color="{AMBER}", penwidth=2];
  subgraph cluster_ev {{ label="Evidence layer"; style="rounded,filled"; fillcolor="#f7f9fc"; color="{NAVY}"; fontcolor="{NAVY}"; labeljust=l;
    store [label="SHA-256 hash and\\nevidence database", fillcolor="white"];
    sign  [label="Ed25519 signature", fillcolor="white"];
    chain [label="Polygon Amoy anchor\\n(optional)", fillcolor="white"];
    pdf   [label="Evidence PDF", fillcolor="white"]; }}
  user -> api;
  api -> meta; api -> img; api -> prov;
  meta -> dec; img -> dec; prov -> dec;
  dec -> store; dec -> sign; dec -> chain; dec -> pdf;
  api -> user [style=dashed, constraint=false];
''')

# 2. methodology (detector) ─────────────────────────────────────────────────────────────
render("fig_method", HEAD + f"""
  label="Detection pipeline of the trained image forensics agent"; rankdir=TB; splines=spline; nodesep=0.55; ranksep=0.7;
  a [label="Input image\\n(native resolution)", fillcolor="{F_AMBER}", color="{AMBER}"];
  b [label="Re-save as JPEG at\\nquality 70, 85 and 95"];
  c [label="Error-level maps\\n|image - re-saved image|\\nstacked as 3 channels"];
  d [label="224 x 224 crops\\n(up to 6 per image,\\nno resizing)"];
  e [label="EfficientNet-B0\\n(ImageNet weights,\\nfine-tuned)", fillcolor="{F_BLUE}", color="{BLUE}", penwidth=2];
  f [label="Average the\\ncrop logits"];
  g [label="p(manipulated)\\nauthenticity = 1 - p", fillcolor="{F_TEAL}", color="{TEAL}", penwidth=2];
  h [label="Decision engine\\nAuthentic >= 0.75\\nFake <= 0.40", fillcolor="{F_AMBER}", color="{AMBER}"];
  {{ rank=same; a; b; c; d; }}
  {{ rank=same; h; g; f; e; }}
  a -> b -> c -> d;
  d -> e;
  h -> g -> f -> e [style=invis];
  e -> f -> g -> h [constraint=false];
""")

# 3. data-flow diagram ──────────────────────────────────────────────────────────────────
def store(label):
    return (f'shape=none, style="", margin=0, label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="7">'
            f'<TR><TD SIDES="TB" BGCOLOR="white"><FONT COLOR="{INK}">{label}</FONT></TD></TR></TABLE>>')


# 5. class diagram ──────────────────────────────────────────────────────────────────────
def cls(name, attrs, methods, fill="white", stereo=""):
    rows = "".join(f'<TR><TD ALIGN="LEFT" BORDER="0">{a}</TD></TR>' for a in attrs) or '<TR><TD BORDER="0"> </TD></TR>'
    mrows = "".join(f'<TR><TD ALIGN="LEFT" BORDER="0"><I>{m}</I></TD></TR>' for m in methods) or '<TR><TD BORDER="0"> </TD></TR>'
    st = f'<FONT POINT-SIZE="9">&laquo;{stereo}&raquo;</FONT><BR/>' if stereo else ""
    return (f'shape=none, style="", margin=0, label=<<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5" COLOR="{NAVY}" BGCOLOR="{fill}">'
            f'<TR><TD BGCOLOR="{NAVY}" BORDER="0"><FONT COLOR="white"><B>{st}{name}</B></FONT></TD></TR>'
            f'<TR><TD BORDER="0" SIDES="B" CELLPADDING="0"><TABLE BORDER="0" CELLSPACING="0" CELLPADDING="3">{rows}</TABLE></TD></TR>'
            f'<TR><TD BORDER="0"><TABLE BORDER="0" CELLSPACING="0" CELLPADDING="3">{mrows}</TABLE></TD></TR></TABLE>>')


render("fig_class_model", HEAD + f'''
  label="Class diagram: evidence data model"; rankdir=TB; splines=ortho; nodesep=0.7; ranksep=0.9;
  ev [{cls("Evidence", ["id : UUID", "original_filename : str", "file_hash : SHA-256", "status : enum", "upload_time : datetime"], ["analyze()"], F_GREY)}];
  ar [{cls("AgentResult", ["agent_name : str", "findings : JSON", "confidence_score : float", "heatmap_path : str", "extras : JSON"], [], F_GREY)}];
  fv [{cls("FinalVerdict", ["verdict : enum", "overall_score : float", "manipulation_type : str", "reasoning : JSON"], [], F_GREY)}];
  al [{cls("AuditLog", ["blockchain_hash : str", "record_signature : str", "signed_payload : JSON", "chain_of_custody : JSON"], ["verify()"], F_GREY)}];
  {{ rank=same; ar; fv; al; }}
  ev -> ar [arrowhead=odiamond, taillabel="1", headlabel="1..*", labeldistance=2.2];
  ev -> fv [arrowhead=diamond, taillabel="1", headlabel="1", labeldistance=2.2];
  ev -> al [arrowhead=diamond, taillabel="1", headlabel="1", labeldistance=2.2];
''')

render("fig_class_agents", HEAD + f"""
  label="Class diagram: agents and decision engine"; rankdir=TB; splines=ortho; nodesep=0.7; ranksep=0.8;
  ag [{cls("Agent", ["name : str"], ["run(path) : dict"], F_AMBER, "interface")}];
  ma [{cls("MetadataAgent", [], ["run(path)"])}];
  ia [{cls("ImageAgent", ["trained_detector"], ["run(path)"], F_BLUE)}];
  sa [{cls("SecurityAgent", [], ["run(path)"])}];
  td [{cls("TrainedDetector", ["backbone : EfficientNet-B0", "weights : .pt file"], ["predict(path) : p_manipulated"], F_TEAL)}];
  de [{cls("DecisionEngine", ["weights : dict", "thresholds : tuple"], ["decide(results) : dict"], F_AMBER)}];
  {{ rank=same; ma; ia; sa; }}
  {{ rank=same; ag; de; }}
  ag -> ma [dir=back, arrowtail=onormal]; ag -> ia [dir=back, arrowtail=onormal]; ag -> sa [dir=back, arrowtail=onormal];
  ia -> td [arrowhead=vee, style=dashed, xlabel="uses  "];
  ag -> de [arrowhead=vee, style=dashed, xlabel="results  ", constraint=false];
""")


CHROME = Path(r"C:\Users\Divyansh Gupta\AppData\Local\Google\Chrome\Application\chrome.exe")


def svg_png(name, W, H, scale=2.5):
    html = OUT / f"_{name}.html"
    html.write_text(f'<html><body style="margin:0;background:white"><img src="{name}.svg" width="{W}" height="{H}"></body></html>', encoding="utf-8")
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}", f"--force-device-scale-factor={scale}",
                    f"--screenshot={OUT / (name + '.png')}", html.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    html.unlink()


def arrow(pts, label=None, lx=0, ly=0, dashed=False, anchor="middle"):
    """Orthogonal arrow along pts with a triangular head at the last point."""
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    dx = (x1 > x0) - (x1 < x0)
    dy = (y1 > y0) - (y1 < y0)
    body = pts[:-1] + [(x1 - dx * 11, y1 - dy * 11)]
    d = " ".join(f"{x},{y}" for x, y in body)
    out = [f'<polyline points="{d}" fill="none" stroke="{GREY}" stroke-width="1.8"' + (' stroke-dasharray="7 5"' if dashed else "") + "/>"]
    if dx:
        out.append(f'<polygon points="{x1},{y1} {x1 - dx * 13},{y1 - 5.5} {x1 - dx * 13},{y1 + 5.5}" fill="{GREY}"/>')
    else:
        out.append(f'<polygon points="{x1},{y1} {x1 - 5.5},{y1 - dy * 13} {x1 + 5.5},{y1 - dy * 13}" fill="{GREY}"/>')
    if label:
        out.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="13" fill="{GREY}">{label}</text>')
    return "\n".join(out)


def dfd():
    W, H = 1340, 640
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, Helvetica, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="white"/>',
         f'<text x="{W / 2}" y="38" text-anchor="middle" font-size="22" font-weight="bold" fill="{INK}">Data-flow diagram, level 1</text>']
    # external entity
    g.append(f'<rect x="40" y="262" width="130" height="64" fill="{F_AMBER}" stroke="{AMBER}" stroke-width="2"/>')
    g.append(f'<text x="105" y="300" text-anchor="middle" font-size="16" font-weight="bold" fill="{INK}">Analyst</text>')
    # processes
    procs = [(330, "1.0", "Ingest and hash"), (620, "2.0", "Forensic agents"), (910, "3.0", "Decision engine"), (1200, "4.0", "Sign, anchor and report")]
    for x, n, t in procs:
        g.append(f'<ellipse cx="{x}" cy="294" rx="98" ry="58" fill="{F_BLUE}" stroke="{NAVY}" stroke-width="2"/>')
        g.append(f'<text x="{x}" y="284" text-anchor="middle" font-size="15" font-weight="bold" fill="{INK}">{n}</text>')
        words = t.split()
        if len(words) > 2:
            g.append(f'<text x="{x}" y="304" text-anchor="middle" font-size="14" fill="{INK}">{" ".join(words[:2])}</text>')
            g.append(f'<text x="{x}" y="322" text-anchor="middle" font-size="14" fill="{INK}">{" ".join(words[2:])}</text>')
        else:
            g.append(f'<text x="{x}" y="308" text-anchor="middle" font-size="14" fill="{INK}">{t}</text>')

    def store(x, y, w, label):
        return (f'<line x1="{x}" y1="{y}" x2="{x + w}" y2="{y}" stroke="{NAVY}" stroke-width="2"/>'
                f'<line x1="{x}" y1="{y + 46}" x2="{x + w}" y2="{y + 46}" stroke="{NAVY}" stroke-width="2"/>'
                f'<text x="{x + w / 2}" y="{y + 29}" text-anchor="middle" font-size="14.5" fill="{INK}">{label}</text>')

    g.append(store(520, 112, 200, "D2  Trained model weights"))
    g.append(store(810, 520, 200, "D1  Evidence store"))
    # flows
    g.append(arrow([(170, 294), (232, 294)], "image file", 201, 282))
    g.append(arrow([(428, 294), (522, 294)], "image", 475, 282))
    g.append(arrow([(718, 294), (812, 294)], "agent scores", 765, 282))
    g.append(arrow([(1008, 294), (1102, 294)], "verdict", 1055, 282))
    g.append(arrow([(620, 158), (620, 236)], "weights", 630, 202, dashed=True, anchor="start"))
    g.append(arrow([(330, 352), (330, 543), (808, 543)], "original file and SHA-256", 560, 534))
    g.append(arrow([(1200, 352), (1200, 543), (1012, 543)], "signed record", 1106, 534))
    g.append(arrow([(1200, 236), (1200, 84), (105, 84), (105, 260)], "report, evidence PDF, verification", 650, 74))
    g.append("</svg>")
    (OUT / "fig_dfd.svg").write_text("\n".join(g), encoding="utf-8")
    svg_png("fig_dfd", W, H)
    print("wrote fig_dfd")


dfd()


def usecase():
    cases = ["Upload an image", "View verdict and score", "Inspect heatmaps (ELA, Grad-CAM)",
             "Download evidence PDF", "Verify signature and file integrity", "Browse analysis history"]
    W, H = 1180, 120 + 78 * len(cases) + 40
    cx, rx, ry = 590, 215, 32
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, Helvetica, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="white"/>',
         f'<text x="{W / 2}" y="38" text-anchor="middle" font-size="22" font-weight="bold" fill="{INK}">Use-case diagram</text>',
         f'<rect x="{cx - rx - 50}" y="64" width="{2 * rx + 100}" height="{H - 84}" rx="14" fill="#fbfcfe" stroke="{NAVY}" stroke-width="2"/>',
         f'<text x="{cx}" y="92" text-anchor="middle" font-size="16" font-weight="bold" fill="{NAVY}">TrustSphere AI</text>']
    ys = [140 + 78 * i for i in range(len(cases))]
    mid = (ys[0] + ys[-1]) / 2

    def actor(x, label):
        out = [f'<circle cx="{x}" cy="{mid - 46}" r="15" fill="white" stroke="{AMBER}" stroke-width="2.4"/>',
               f'<line x1="{x}" y1="{mid - 31}" x2="{x}" y2="{mid + 14}" stroke="{AMBER}" stroke-width="2.4"/>',
               f'<line x1="{x - 24}" y1="{mid - 16}" x2="{x + 24}" y2="{mid - 16}" stroke="{AMBER}" stroke-width="2.4"/>',
               f'<line x1="{x}" y1="{mid + 14}" x2="{x - 20}" y2="{mid + 50}" stroke="{AMBER}" stroke-width="2.4"/>',
               f'<line x1="{x}" y1="{mid + 14}" x2="{x + 20}" y2="{mid + 50}" stroke="{AMBER}" stroke-width="2.4"/>']
        for k, t in enumerate(label):
            out.append(f'<text x="{x}" y="{mid + 76 + 19 * k}" text-anchor="middle" font-size="15" font-weight="bold" fill="{INK}">{t}</text>')
        return out
    for i, (t, y) in enumerate(zip(cases, ys)):
        g.append(f'<line x1="150" y1="{mid - 8}" x2="{cx - rx}" y2="{y}" stroke="#9aa7b8" stroke-width="1.6"/>')
        if i in (1, 3, 4):
            g.append(f'<line x1="{W - 150}" y1="{mid - 8}" x2="{cx + rx}" y2="{y}" stroke="#9aa7b8" stroke-width="1.6"/>')
    for t, y in zip(cases, ys):
        g.append(f'<ellipse cx="{cx}" cy="{y}" rx="{rx}" ry="{ry}" fill="{F_BLUE}" stroke="{NAVY}" stroke-width="1.8"/>')
        g.append(f'<text x="{cx}" y="{y + 5}" text-anchor="middle" font-size="15" fill="{INK}">{t}</text>')
    g += actor(110, ["Analyst /", "investigator"]) + actor(W - 110, ["Verifier /", "auditor"])
    g.append("</svg>")
    (OUT / "fig_usecase.svg").write_text("\n".join(g), encoding="utf-8")
    svg_png("fig_usecase", W, H)
    print("wrote fig_usecase")


usecase()

# 6. sequence diagram (hand-built SVG) ──────────────────────────────────────────────────
lanes = [("Analyst", 90), ("Web app", 270), ("FastAPI", 450), ("Agents", 630), ("Decision engine", 810), ("Evidence store", 990)]
msgs = [(0, 1, "choose and submit image", False), (1, 2, "POST /api/upload", False), (2, 5, "hash and store file", False),
        (2, 3, "run metadata, image, provenance", False), (3, 3, "trained detector, ELA, Grad-CAM", None), (3, 4, "agent scores", False),
        (4, 2, "verdict and reasoning", True), (2, 5, "sign and save record", False), (2, 1, "file_id", True),
        (1, 2, "GET /api/report and /api/verify", False), (2, 1, "report JSON, verification", True), (1, 0, "verdict, heatmaps, evidence PDF", True)]
W, top, step = 1120, 120, 62
H = top + step * (len(msgs) + 1)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, Helvetica, sans-serif">',
       f'<rect width="{W}" height="{H}" fill="white"/>',
       f'<text x="{W / 2}" y="40" text-anchor="middle" font-size="22" font-weight="bold" fill="{INK}">Sequence diagram: analysing one image</text>',
       ]
for name, x in lanes:
    svg.append(f'<rect x="{x - 70}" y="62" width="140" height="42" rx="8" fill="{F_BLUE}" stroke="{NAVY}" stroke-width="1.6"/>')
    svg.append(f'<text x="{x}" y="88" text-anchor="middle" font-size="15" font-weight="bold" fill="{INK}">{name}</text>')
    svg.append(f'<line x1="{x}" y1="104" x2="{x}" y2="{H - 20}" stroke="#aab6c6" stroke-width="1.4" stroke-dasharray="6 5"/>')
for k, (a, b, text, ret) in enumerate(msgs):
    y = top + step * (k + 1)
    xa, xb = lanes[a][1], lanes[b][1]
    svg.append(f'<text x="{(xa + xb) / 2 if a != b else xa + 18}" y="{y - 12}" text-anchor="{"middle" if a != b else "start"}" font-size="13.5" fill="{INK}">{k + 1}. {text}</text>')
    if a == b:
        svg.append(f'<rect x="{xa - 8}" y="{y - 6}" width="16" height="40" fill="{F_BLUE}" stroke="{NAVY}" stroke-width="1.4"/>')
    else:
        d = ' stroke-dasharray="7 5"' if ret else ""
        sgn = 1 if xb > xa else -1
        tip = xb - sgn * 2
        svg.append(f'<line x1="{xa}" y1="{y}" x2="{tip - sgn * 11}" y2="{y}" stroke="{GREY}" stroke-width="1.8"{d}/>')
        svg.append(f'<polygon points="{tip},{y} {tip - sgn * 13},{y - 5.5} {tip - sgn * 13},{y + 5.5}" fill="{GREY}"/>')
svg.append("</svg>")
(OUT / "fig_sequence.svg").write_text("\n".join(svg), encoding="utf-8")
svg_png("fig_sequence", W, H)
print("wrote fig_sequence")
