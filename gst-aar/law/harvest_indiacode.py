#!/usr/bin/env python3
"""India Code (DSpace 7) section harvester.

India Code has migrated: `indiacode.nic.in` now only serves a redirect page
pointing at **`indiacode.gov.in`**. The old site was DSpace 5.5 with JSP scraping;
the new one is DSpace 7 with a REST API, and the old scrapers in
`scripts/legislation/` target endpoints that no longer exist.

The CENTRAL community has a dedicated **`Section` collection** where every section
of every central Act is a separate item carrying:

    dc.identifier.act_name                 -> parent Act
    dc.identifier.section_number           -> e.g. "11A", "149"
    dc.title                               -> section heading
    dc.identifier.section_page_note        -> the section TEXT (HTML)
    dc.identifier.repealed                 -> true/false

So the wording can be read straight off the API — no bitstream download, no OCR.

This harvests the sections of the Acts already held in the CBIC statute hierarchy
so the two can be joined.

Usage: python3 harvest_indiacode.py                (all target acts, resumable)
       python3 harvest_indiacode.py --only cgst
Output: gst-aar/data/law/indiacode/sections.jsonl
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
OUT = ROOT / "data" / "law" / "indiacode"
SECTIONS = OUT / "sections.jsonl"

BASE = "https://indiacode.gov.in/server/api"
CENTRAL_SECTION_COLLECTION = "9a5b5f4a-4ccf-4cef-9820-0d33f8a6707f"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
      "Accept": "application/json"}
PAGE = 100

# --- shared per-host politeness limiter (see _throttle.py) ---
try:
    import _throttle as _thr
except ImportError:  # imported as a module under pytest, not as a script
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location("_throttle", Path(__file__).parent / "_throttle.py")
    _thr = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_thr)

# key -> (search query, normalised Act name we accept)
# The query is what India Code's discover index matches; the second value is the
# normalised `dc.identifier.act_name` we keep, so a query returning several Acts
# cannot contaminate the result.
TARGETS = {
    "customs":        ("Customs Act 1962", "customs act 1962"),
    "cgst":           ("Central Goods and Services Tax Act 2017",
                       "central goods and services tax act 2017"),
    "excise":         ("Central Excise Act 1944", "central excise act 1944"),
    "customs_tariff": ("Customs Tariff Act 1975", "customs tariff act 1975"),
    "cgst_jk":        ("Central Goods and Services Tax Extension Jammu Kashmir",
                       "central goods and services tax extension to jammu and kashmir act 2017"),
    "igst_jk":        ("Integrated Goods and Services Tax Extension Jammu Kashmir",
                       "integrated goods and services tax extension to jammu and kashmir act 2017"),
    "compensation":   ("Goods and Services Tax Compensation to States Act 2017",
                       "goods and services tax compensation to states act 2017"),
    "igst":           ("Integrated Goods and Services Tax Act 2017",
                       "integrated goods and services tax act 2017"),
    "utgst":          ("Union Territory Goods and Services Tax Act 2017",
                       "union territory goods and services tax act 2017"),
    "constitution101": ("Constitution One Hundred and First Amendment Act 2016",
                        "constitution one hundred and first amendment act 2016"),
    # Foreign Trade (Development and Regulation) Act, 1992 — the CBIC hierarchy
    # carries 21 of its sections but with no Act name recorded, which is why they
    # were unmatched. Identified from the section headings themselves
    # ("Export and import policy", "Importer-exporter Code Number").
    "ftdr":           ("Foreign Trade Development and Regulation Act 1992",
                       "foreign trade development and regulation act 1992"),
    # India Code titles this Act with the year 2023, not 1931 — another of its
    # quirks (cf. Kerala's "Gooda"). Section titles match the CBIC rows 1:1, so it
    # is the same Act; the join records the India Code name so the discrepancy is
    # visible rather than hidden.
    "provisional":    ("Provisional collection of Taxes",
                       "provisional collection of taxes act 2023"),
}


def _get(url: str, retries: int = 3) -> dict:
    for i in range(retries):
        _thr.wait(url)
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=90) as r:
                blob = r.read()
            _thr.on_success(url)
            return json.loads(blob)
        except Exception as e:
            _thr.on_error(url, e)
            if i == retries - 1:
                raise
            print(f"  retry {i + 1}: {type(e).__name__}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def clean_text(note: str) -> str:
    """section_page_note is HTML; strip tags and decode entities."""
    t = re.sub(r"<br\s*/?>", "\n", note or "", flags=re.I)
    t = re.sub(r"</p>", "\n\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = t.replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _field(md: dict, key: str) -> str:
    v = md.get(key)
    return v[0]["value"] if v else ""


def search_sections(query: str, page: int) -> dict:
    url = (f"{BASE}/discover/search/objects"
           f"?scope={CENTRAL_SECTION_COLLECTION}"
           f"&query={urllib.parse.quote(query)}&size={PAGE}&page={page}")
    return _get(url)


def harvest_act(key: str, query: str, accept: str) -> list[dict]:
    """All sections of one Act, filtered on the exact parent Act name."""
    found, page = {}, 0
    while True:
        d = search_sections(query, page)
        sr = d["_embedded"]["searchResult"]
        objs = sr["_embedded"]["objects"]
        if not objs:
            break
        for o in objs:
            ind = o["_embedded"]["indexableObject"]
            md = ind.get("metadata", {})
            if norm(_field(md, "dc.identifier.act_name")) != accept:
                continue
            num = _field(md, "dc.identifier.section_number")
            text = clean_text(_field(md, "dc.identifier.section_page_note"))
            if not num or not text:
                continue
            found[num] = {
                "key": key,
                "act_name": _field(md, "dc.identifier.act_name"),
                "section_number": num,
                "title": _field(md, "dc.title"),
                "repealed": _field(md, "dc.identifier.repealed"),
                "uuid": ind.get("uuid"),
                "text": text,
            }
        total = sr["page"]["totalElements"]
        page += 1
        if page * PAGE >= total or page > 60:
            break
    return list(found.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated target keys")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    only = {s for s in args.only.split(",") if s}
    keys = [k for k in TARGETS if not only or k in only]

    grand = 0
    with SECTIONS.open("a") as log:
        for key in keys:
            query, accept = TARGETS[key]
            try:
                rows = harvest_act(key, query, accept)
            except Exception as e:
                print(f"{key:16s} FAILED {type(e).__name__}: {str(e)[:70]}",
                      file=sys.stderr)
                continue
            for r in rows:
                log.write(json.dumps(r, ensure_ascii=False) + "\n")
            log.flush()
            grand += len(rows)
            print(f"  {key:16s} {len(rows):>4} sections", flush=True)

    print(f"\nharvested {grand} sections -> {SECTIONS}")


if __name__ == "__main__":
    main()
