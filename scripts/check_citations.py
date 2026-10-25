"""Check the citations of the built report.

    python scripts/check_citations.py

1. citations are numbered in order of first appearance (1, 2, 3, ...), with no gaps
2. groups are written like the conference paper: [3], [3, 4], [5-9] (never [5], [6], [7] or [5, 6, 7])
3. every reference in the list is cited and every cited number exists
4. a name or method mentioned right before a citation is the reference that is cited
"""
import json
import re
import sys
from pathlib import Path

import docx
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent
D = docx.Document(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "docs" / "report" / "TrustSphere_AI_Project_Report.docx"))
REFMAP = json.loads((ROOT / "docs" / "report" / "citation_map.json").read_text(encoding="utf-8"))   # new number -> reference text

# method / dataset names and a distinctive piece of the title of the reference that must be cited with them
NAMES = {"Splicebuster": "Splicebuster", "BusterNet": "BusterNet", "ManTra-Net": "ManTra-Net", "RRU-Net": "RRU-Net", "PSCC-Net": "PSCC-Net",
         "MVSS-Net": "multi-view multi-scale", "CAT-Net": "JPEG compression artifacts", "ObjectFormer": "ObjectFormer", "TruFor": "TruFor",
         "JPEG ghosts": "JPEG ghosts", "Grad-CAM": "Grad-CAM", "C2PA": "C2PA", "AdamW": "Decoupled weight decay", "Residual networks": "residual learning",
         "vision transformers": "16x16 words", "U-Net": "U-Net"}
NAMES_END = {"CASIA": "CASIA image tampering", "Columbia splicing set": "geometry invariants", "spliced blocks": "authentic and spliced image blocks",
             "CoMoFoD": "CoMoFoD", "COVERAGE": "COVERAGE", "image database": "Dresden", "EfficientNet backbone": "EfficientNet", "Ed25519 key": "signatures"}

CITE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")


def body_texts():
    """Paragraph and table-cell texts of the body, in document order, from CHAPTER 1 to the reference list."""
    out, on = [], False
    for el in D.element.body:
        if el.tag == qn("w:p"):
            texts = ["".join(t.text or "" for t in el.iter(qn("w:t")))]
        elif el.tag == qn("w:tbl"):
            texts = ["".join(t.text or "" for t in tc.iter(qn("w:t"))) for tc in el.iter(qn("w:tc"))]
        else:
            continue
        for t in texts:
            if t.strip() == "CHAPTER 1":
                on = True
            if t.strip().startswith("CHAPTER 9"):
                return out
            if on:
                out.append(t)
    return out


def expand(group):
    nums = []
    for part in group.split(","):
        part = part.strip()
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            nums += list(range(a, b + 1))
        else:
            nums.append(int(part))
    return nums


def surnames(ref):
    authors = ref.split('"')[0].strip().rstrip(",")
    names = [n.strip() for n in re.split(r",| and ", authors) if n.strip() and n.strip() != "et al."]
    return [n.split()[-1].replace("et", "").strip() or n.split()[-2] for n in names]


def main():
    texts = body_texts()
    problems, seen, order = [], [], []
    for t in texts:
        for m in CITE.finditer(t):
            nums = expand(m.group(1))
            for n in nums:
                if n not in seen:
                    seen.append(n)
            # format: three or more consecutive numbers must be a range, two are a comma list
            body = m.group(1)
            if re.search(r"\d+\s*,\s*\d+\s*,\s*\d+", body) and any(b == a + 1 and c == b + 1 for a, b, c in zip(nums, nums[1:], nums[2:])):
                problems.append(f"consecutive numbers not written as a range: [{body}]")
    for a, b in zip(seen, seen[1:]):
        if b != a + 1:
            problems.append(f"citations are not serial: {a} is followed by {b} on first appearance")
    if seen[:1] != [1]:
        problems.append("first citation is not [1]")
    if re.search(r"\]\s*,\s*\[|\]\s*(to|and)\s*\[", "\n".join(texts)):
        problems.append("adjacent separate brackets such as [1], [2] or [1] to [4] found")
    never = [n for n in map(int, REFMAP) if n not in seen]
    beyond = [n for n in seen if str(n) not in REFMAP]
    if never:
        problems.append(f"references never cited: {never}")
    if beyond:
        problems.append(f"citations without a reference: {beyond}")

    # the reference list in the document must be in the same order as the map
    paras = [p.text.strip() for p in D.paragraphs]
    start = next(i for i, t in enumerate(paras) if t.startswith("9. REFERENCES")) + 1
    listed = [t for t in paras[start:] if t][:len(REFMAP)]
    for i, t in enumerate(listed, 1):
        if t != REFMAP[str(i)]:
            problems.append(f"reference list entry {i} differs from the citation map")

    # a name or method written right before a citation must be the reference that is cited
    authors = {int(k): surnames(v) for k, v in REFMAP.items()}
    for t in texts:
        prev_end = 0
        for m in CITE.finditer(t):
            seg = t[prev_end:m.start()]
            seg = seg[seg.rfind(". ") + 2:] if ". " in seg else seg
            prev_end = m.end()
            cited = expand(m.group(1))
            cited_refs = [REFMAP[str(n)] for n in cited if str(n) in REFMAP]
            for n, names in authors.items():
                first = names[0]
                if re.search(rf"\b{re.escape(first)}\b( et al\.| and [A-Z][\wÀ-ſ]+)", seg):
                    ok = any(surnames(r)[0] == first for r in cited_refs)
                    if not ok and n not in cited and first not in {"Chen", "Wu"}:
                        problems.append(f"'{first}' mentioned before [{m.group(1)}] but the cited reference is by {[surnames(r)[0] for r in cited_refs]}")
            for name, piece in NAMES.items():
                if name in seg and not any(piece.lower() in r.lower() for r in cited_refs):
                    problems.append(f"'{name}' mentioned before [{m.group(1)}] but no cited reference matches '{piece}'")
            for name, piece in NAMES_END.items():
                if seg.rstrip().endswith(name) and not any(piece.lower() in r.lower() for r in cited_refs):
                    problems.append(f"'{name}' directly before [{m.group(1)}] but no cited reference matches '{piece}'")
    print(f"citations found: {len(seen)} different, first appearance order {seen[:12]}...")
    print("references in the list:", len(REFMAP))
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("all citation checks passed")


if __name__ == "__main__":
    main()
