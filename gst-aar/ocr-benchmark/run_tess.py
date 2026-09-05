"""Run tesseract variants and score ground-truth facts."""
import subprocess, time, glob, os, re, sys, json

OUT = "/Users/vishalkumar/Downloads/qlaw/gst-aar/ocr-benchmark/texts"

FACTS = {
    "ruling": lambda t: bool(re.search(r"RAJ\s*/\s*AAR", t, re.I)),
    "date": lambda t: bool(re.search(r"30[.\-/ ]0?7[.\-/ ]2026", t)),
    "allen": lambda t: bool(re.search(r"allen", t, re.I)),
    "institute_full": lambda t: bool(re.search(r"allen\s+career\s+institute", t, re.I)),
    "hsn_mentions": lambda t: len(re.findall(r"HSN", t, re.I)),
    "hsn_codes": lambda t: len(re.findall(r"\b\d{4,8}\b", t)),
    "notif_132020": lambda t: bool(re.search(r"13\s*/\s*2020", t)),
    "einvoice": lambda t: bool(re.search(r"e[- ]?invoic", t, re.I)),
    "rajasthan": lambda t: bool(re.search(r"rajasthan", t, re.I)),
    "garbled_ratio": None,  # computed separately
}

def garbled_ratio(text):
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 8]
    if not lines:
        return 1.0
    bad = 0
    for l in lines:
        alnum = sum(c.isalnum() or c.isspace() or c in ".,;:()/-%&'" for c in l)
        if alnum / len(l) < 0.75:
            bad += 1
    return bad / len(lines)

def run_variant(imgdir, name, langs="eng", extra=None, pages=None):
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(f"{imgdir}/*.png"))
    if pages:
        files = [f for f in files if int(re.search(r"p(\d+)", os.path.basename(f)).group(1)) in pages]
    t0 = time.time()
    texts = []
    for f in files:
        outbase = os.path.join(OUT, name, os.path.basename(f)[:-4])
        os.makedirs(os.path.dirname(outbase), exist_ok=True)
        cmd = ["tesseract", f, outbase, "-l", langs]
        if extra:
            cmd += extra
        subprocess.run(cmd, check=True, capture_output=True)
        with open(outbase + ".txt") as fh:
            texts.append((os.path.basename(f), fh.read()))
    dt = time.time() - t0
    full = "\n\n".join(t for _, t in texts)
    scores = {k: (fn(full) if fn else None) for k, fn in FACTS.items()}
    scores["garbled_ratio"] = round(garbled_ratio(full), 3)
    scores["chars"] = len(full)
    scores["s_per_page"] = round(dt / len(files), 2)
    with open(os.path.join(OUT, f"_{name}_full.txt"), "w") as fh:
        fh.write(full)
    print(json.dumps({name: scores}, indent=1))
    return full

if __name__ == "__main__":
    imgdir = sys.argv[1]
    name = sys.argv[2]
    langs = sys.argv[3] if len(sys.argv) > 3 else "eng"
    extra = sys.argv[4].split() if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    run_variant(imgdir, name, langs, extra)
