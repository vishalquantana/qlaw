#!/usr/bin/env python3
"""Stream C (metadata-first): GST Council + eGazette + GSTN advisory links.

Downloads nothing in bulk on first pass — records .gov.in PDF links as rows
with empty body; body filled by the OCR/text pass (Vision pipeline reuse).
"""
from __future__ import annotations

import re
import urllib.parse

COUNCIL_INDEX = "https://gstcouncil.gov.in/"
LINK_RE = re.compile(r'href="([^"]+)"[^>]*>([^<]{4,200})', re.I)


def parse_links(html: str, base_url: str) -> list[dict]:
    rows = []
    for m in LINK_RE.finditer(html):
        url = urllib.parse.urljoin(base_url, m.group(1))
        if ".gov.in" not in url:
            continue
        if not url.lower().endswith(".pdf"):
            continue
        rows.append({"title": " ".join(m.group(2).split()), "pdf_url": url})
    return rows
