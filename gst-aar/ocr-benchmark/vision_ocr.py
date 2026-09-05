"""macOS Vision OCR via PyObjC on rendered page images."""
import subprocess, time, glob, os, sys
import Vision
import Quartz
from Foundation import NSURL, NSData

def ocr_image(path):
    url = NSURL.fileURLWithPath_(path)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(["en-IN", "hi-IN"])
    req.setUsesLanguageCorrection_(True)
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    ok = handler.performRequests_error_([req], None)
    results = req.results() or []
    lines = []
    for obs in results:
        cand = obs.topCandidates_(1)
        if cand:
            lines.append(cand[0].string())
    return "\n".join(lines)

if __name__ == "__main__":
    imgdir = sys.argv[1]
    outname = sys.argv[2]
    files = sorted(glob.glob(f"{imgdir}/*.png"))
    os.makedirs("texts", exist_ok=True)
    t0 = time.time()
    texts = []
    for f in files:
        texts.append(ocr_image(f))
    dt = time.time() - t0
    full = "\n\n".join(texts)
    with open(f"texts/_{outname}_full.txt", "w") as fh:
        fh.write(full)
    print(f"{outname}: {len(files)} pages in {dt:.1f}s ({dt/len(files):.2f} s/page), {len(full)} chars")
