"""Shared HTTPS for gov portals: legacy-renegotiation + bundled intermediates.

Several Indian gov hosts (comtax.wb.gov.in, tgct.gov.in, taxinformation.cbic.gov.in)
either require unsafe legacy renegotiation (disabled in OpenSSL 3.x) or omit
intermediate certs (which OpenSSL, unlike macOS SecureTransport, will not chase
via AIA). This helper centralizes both workarounds. Verification stays ON.
"""
from __future__ import annotations

import http.cookiejar
import ssl
import urllib.request
from pathlib import Path

CERTS_DIR = Path(__file__).parent / "certs"


def context() -> ssl.SSLContext:
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    if getattr(ssl, "OP_LEGACY_SERVER_CONNECT", None) is not None:
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    if CERTS_DIR.exists():
        for pem in sorted(CERTS_DIR.glob("*.pem")):
            try:
                ctx.load_verify_locations(cafile=str(pem))
            except ssl.SSLError:
                continue  # not a CA bundle (e.g. leaf-only file) — skip
    return ctx


def session() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context()),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
