"""Unified scoring across all extracted full texts."""
import re, glob, os

def dev(t): return len(re.findall(r"[\u0900-\u097F]", t))

def garbled(text):
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 8]
    if not lines: return 1.0
    bad = sum(1 for l in lines if sum(c.isalnum() or c.isspace() or c in ".,;:()/-%&'।" for c in l)/len(l) < 0.75)
    return round(bad/len(lines), 3)

def score(path):
    t = open(path).read()
    return {
        "RAJ/AAR ruling no": "PASS" if re.search(r"RAJ\s*/\s*AAR\s*/\s*2026-27\s*/\s*11", t) else ("partial" if re.search(r"AAR\s*/\s*2026-27", t) else "FAIL"),
        "date 30.07.2026": "PASS" if re.search(r"30[.\-/ ]0?7[.\-/ ]2026", t) else "FAIL",
        "Allen applicant": "PASS" if re.search(r"allen\s+career\s+institute", t, re.I) else "FAIL",
        "GSTIN exact": "PASS" if "08AAVCA8216C1ZI" in t else ("near" if re.search(r"08AAVCA8216C1Z.", t) else "FAIL"),
        "13/2020 notif": "PASS" if re.search(r"13\s*/\s*2020", t) else "FAIL",
        "e-invoicing": "PASS" if re.search(r"e[- ]?invoic", t, re.I) else "FAIL",
        "garbled line frac": garbled(t),
        "devanagari chars": dev(t),
        "chars": len(t),
    }

if __name__ == "__main__":
    targets = sorted(glob.glob("texts/_tess*_full.txt")) + ["texts/ocrmypdf-sidecar.txt"] + sorted(glob.glob("texts/_vision*_full.txt"))
    for p in targets:
        name = os.path.basename(p).replace("_full.txt","").replace(".txt","").lstrip("_")
        s = score(p)
        print(f"--- {name}")
        for k, v in s.items():
            print(f"    {k}: {v}")
