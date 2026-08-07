#!/usr/bin/env python
"""
Download the real SEBI master circulars this project is evaluated against.

Problem Statement 2 asks solutions to name the regulatory corpus they worked
with, and suggests SEBI's master circulars for stock brokers and/or investment
advisers. This script fetches them straight from sebi.gov.in so the corpus is
reproducible rather than a file someone happened to have on disk.

Usage:
    python scripts/fetch_sebi_corpus.py                # stock brokers + advisers
    python scripts/fetch_sebi_corpus.py --all          # every master circular listed
    python scripts/fetch_sebi_corpus.py --list         # show what is available
"""
import argparse
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sebi_corpus"

LISTING_URL = ("https://www.sebi.gov.in/sebiweb/home/HomeAction.do"
               "?doListing=yes&sid=1&ssid=6&smid=0")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RegGraph/1.0; compliance research)"}

# The corpora PS2 names explicitly.
DEFAULT_TARGETS = ["stock-brokers", "investment-advisers"]

_DETAIL_RE = re.compile(
    r'href="(https://www\.sebi\.gov\.in/legal/master-circulars/[^"]+\.html)"')
_PDF_RE = re.compile(r'https://www\.sebi\.gov\.in/sebi_data/attachdocs/[^"\'\s>]+\.pdf')
_TITLE_RE = re.compile(r'<title>\s*SEBI\s*\|\s*([^<]+)</title>')


def fetch(url: str, client: httpx.Client, tries: int = 3) -> Optional[bytes]:
    for attempt in range(tries):
        try:
            r = client.get(url, headers=HEADERS, timeout=90.0, follow_redirects=True)
            r.raise_for_status()
            return r.content
        except Exception as exc:
            if attempt == tries - 1:
                print(f"    ! failed: {exc}")
                return None
            time.sleep(2 ** attempt)
    return None


def list_master_circulars(client: httpx.Client) -> List[Tuple[str, str]]:
    """Return [(slug, detail_url)] for the master circulars on the listing page."""
    body = fetch(LISTING_URL, client)
    if not body:
        return []
    html = body.decode("utf-8", errors="replace")
    seen: Dict[str, str] = {}
    for url in _DETAIL_RE.findall(html):
        slug = url.rsplit("/", 1)[-1].replace(".html", "")
        # The listing carries several years; keep the newest entry per document,
        # which is the first occurrence (the page is ordered newest first).
        base = re.sub(r'_\d+$', '', slug)
        seen.setdefault(base, url)
    return sorted(seen.items())


def download_one(slug: str, detail_url: str, client: httpx.Client) -> Optional[Path]:
    page = fetch(detail_url, client)
    if not page:
        return None
    html = page.decode("utf-8", errors="replace")

    m = _PDF_RE.search(html)
    if not m:
        print(f"    ! no PDF link on {detail_url}")
        return None
    title_m = _TITLE_RE.search(html)
    title = title_m.group(1).strip() if title_m else slug

    pdf = fetch(m.group(0), client)
    if not pdf:
        return None
    if not pdf[:5].startswith(b"%PDF"):
        print(f"    ! {m.group(0)} did not return a PDF")
        return None

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{slug}.pdf"
    path.write_bytes(pdf)
    print(f"    ✓ {title}")
    print(f"      {path.relative_to(ROOT)}  ({len(pdf) / 1024 / 1024:.1f} MB)")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true",
                    help="download every master circular on the listing page")
    ap.add_argument("--list", action="store_true",
                    help="list what is available without downloading")
    ap.add_argument("--match", nargs="*", default=None,
                    help="substrings to match against the slug "
                         f"(default: {' '.join(DEFAULT_TARGETS)})")
    args = ap.parse_args()

    with httpx.Client() as client:
        print(f"Fetching listing from sebi.gov.in …")
        available = list_master_circulars(client)
        if not available:
            print("Could not read the SEBI listing page. Check your network connection.")
            return 1
        print(f"{len(available)} master circulars listed.\n")

        if args.list:
            for slug, url in available:
                print(f"  {slug}")
            return 0

        targets = args.match if args.match is not None else DEFAULT_TARGETS
        if args.all:
            chosen = available
        else:
            chosen = [(s, u) for s, u in available
                      if any(t.lower() in s.lower() for t in targets)]
            if not chosen:
                print(f"Nothing matched {targets}. Run with --list to see the slugs.")
                return 1

        print(f"Downloading {len(chosen)} document(s) → {OUT.relative_to(ROOT)}/\n")
        ok = 0
        for slug, url in chosen:
            print(f"  {slug}")
            if download_one(slug, url, client):
                ok += 1

    print(f"\n{ok}/{len(chosen)} downloaded.")
    if ok:
        print("\nNext: upload one on the Document Intelligence page, or run")
        print("  python scripts/evaluate_model.py")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
