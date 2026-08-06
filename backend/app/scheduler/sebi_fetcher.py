"""
SEBI Circular Auto-Fetcher — Track 3
Scrapes SEBI's circulars and master circulars listing pages, downloads new PDFs,
extracts text, and feeds them into the RegGraph processing pipeline.

Sources:
  Circulars:        ssid=7  https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0
  Master Circulars: ssid=6  https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=6&smid=0

Flow per run:
  1. Fetch listing page HTML → parse table rows (title, date, detail-page URL)
  2. For each new entry (not in seen_circulars.json):
     a. Fetch detail page → extract PDF URL from /sebi_data/attachdocs/...pdf
     b. Download PDF bytes
     c. pdfplumber → extract text
     d. Call orchestrator.process_circular()
     e. Mark as seen in seen_circulars.json
  3. Write fetch_status.json with last run result
"""
import io
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import httpx
import pdfplumber
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL        = "https://www.sebi.gov.in"
CIRCULARS_URL   = f"{BASE_URL}/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0"
MASTER_CIRC_URL = f"{BASE_URL}/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=6&smid=0"

DATA_DIR          = Path(os.getenv("DATA_DIR", "./data"))
SEEN_PATH         = DATA_DIR / "seen_circulars.json"
STATUS_PATH       = DATA_DIR / "fetch_status.json"
PDF_CACHE_DIR     = DATA_DIR / "fetched_pdfs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Default intermediary types to assign to auto-fetched circulars
DEFAULT_INTERMEDIARY_TYPES = [
    "stockbroker", "depository", "listed_company",
    "investment_adviser", "rta",
]


# ─── Seen-circulars registry ──────────────────────────────────────────────────

def _load_seen() -> Dict[str, dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SEEN_PATH.exists():
        try:
            return json.loads(SEEN_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_seen(seen: Dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, indent=2, default=str))


def _save_status(status: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, default=str))


def load_status() -> dict:
    if STATUS_PATH.exists():
        try:
            return json.loads(STATUS_PATH.read_text())
        except Exception:
            pass
    return {"last_run": None, "status": "never_run", "ingested": 0, "errors": 0}


# ─── HTML scraping ────────────────────────────────────────────────────────────

def _scrape_listing(url: str, circular_type: str) -> List[Dict]:
    """
    Fetch the listing page and return list of:
      {"title": str, "date": str, "detail_url": str, "circular_type": str}
    """
    try:
        with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch listing {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    entries = []

    # The listing table has rows where each row contains a date cell and a link cell
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        link_tag = cells[-1].find("a", href=True)
        if not link_tag:
            continue
        href = link_tag["href"]
        if not href.startswith("http"):
            href = BASE_URL + href
        # Only include actual circular detail pages (not javascript: links)
        if "javascript" in href.lower():
            continue
        title = link_tag.get_text(strip=True)
        if not title:
            continue
        date_text = cells[0].get_text(strip=True)
        entries.append({
            "title":         title,
            "date":          date_text,
            "detail_url":    href,
            "circular_type": circular_type,
        })

    logger.info(f"Scraped {len(entries)} entries from {circular_type} listing")
    return entries


def _extract_pdf_url(detail_url: str) -> Optional[str]:
    """
    Fetch the detail page and extract the PDF URL.
    Pattern: /sebi_data/attachdocs/<month-year>/<timestamp>.pdf
    """
    try:
        with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            resp = client.get(detail_url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch detail page {detail_url}: {e}")
        return None

    # Find PDF link in raw HTML
    pdf_match = re.search(
        r'(sebi_data/attachdocs/[^"\'<>\s]+\.(?:pdf|PDF))',
        html,
        re.IGNORECASE,
    )
    if pdf_match:
        path = pdf_match.group(1)
        return f"{BASE_URL}/{path}" if not path.startswith("http") else path

    # Fallback: look for any .pdf href
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            if not href.startswith("http"):
                href = BASE_URL + href
            return href

    logger.warning(f"No PDF found on detail page: {detail_url}")
    return None


def _download_pdf(pdf_url: str) -> Optional[bytes]:
    """Download PDF bytes from URL."""
    try:
        with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
            resp = client.get(pdf_url)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.warning(f"Failed to download PDF {pdf_url}: {e}")
        return None


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {e}")
        # Fallback: decode as latin-1
        text = pdf_bytes.decode("latin-1", errors="ignore")
    return text.strip()


def _make_circular_id(title: str, date: str) -> str:
    """Generate a stable circular_id from title + date."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower())[:50]
    date_slug = re.sub(r"[^0-9a-zA-Z]", "", date)[:10]
    return f"SEBI_{date_slug}_{slug}".strip("_")


# ─── Main fetch function ──────────────────────────────────────────────────────

def run_fetch(
    orchestrator,
    max_new: int = 5,
    intermediary_types: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict:
    """
    Main entry point for the auto-fetcher.

    Args:
        orchestrator:       RegGraphOrchestrator instance
        max_new:            Max new circulars to process per run (safety cap)
        intermediary_types: Override default intermediary types
        dry_run:            If True, scrape and detect new items but don't process

    Returns:
        Status dict with counts and details of this run
    """
    intermediary_types = intermediary_types or DEFAULT_INTERMEDIARY_TYPES
    seen = _load_seen()
    run_start = datetime.now()

    results = {
        "started_at":   run_start.isoformat(),
        "finished_at":  None,
        "ingested":     [],
        "skipped":      [],
        "errors":       [],
        "dry_run":      dry_run,
    }

    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Scrape both listing pages ─────────────────────────────────
    all_entries: List[Dict] = []
    for url, ctype in [
        (CIRCULARS_URL,   "circular"),
        (MASTER_CIRC_URL, "master_circular"),
    ]:
        entries = _scrape_listing(url, ctype)
        all_entries.extend(entries)
        time.sleep(1.5)  # polite delay between page requests

    logger.info(f"Total entries scraped: {len(all_entries)}")

    # ── Step 2: Filter to new entries only ────────────────────────────────
    new_entries = [e for e in all_entries if e["detail_url"] not in seen]
    logger.info(f"New entries (not yet ingested): {len(new_entries)}")

    if not new_entries:
        results["finished_at"] = datetime.now().isoformat()
        results["message"] = "No new circulars found."
        _save_status({"last_run": run_start.isoformat(), "status": "ok_nothing_new",
                      "ingested": 0, "errors": 0, "details": results})
        return results

    # Cap to max_new to avoid overwhelming the pipeline in one run
    to_process = new_entries[:max_new]
    logger.info(f"Processing up to {len(to_process)} new entries (cap={max_new})")

    # ── Step 3: Process each new entry ────────────────────────────────────
    for entry in to_process:
        detail_url = entry["detail_url"]
        title      = entry["title"]
        date_str   = entry["date"]
        ctype      = entry["circular_type"]

        logger.info(f"Processing [{ctype}] {title[:70]}")

        try:
            # 3a. Get PDF URL from detail page
            time.sleep(1.0)  # polite delay
            pdf_url = _extract_pdf_url(detail_url)
            if not pdf_url:
                results["errors"].append({"title": title, "reason": "No PDF found on detail page"})
                continue

            if dry_run:
                results["ingested"].append({
                    "title":      title,
                    "date":       date_str,
                    "type":       ctype,
                    "pdf_url":    pdf_url,
                    "dry_run":    True,
                })
                seen[detail_url] = {
                    "title": title, "date": date_str, "type": ctype,
                    "pdf_url": pdf_url, "processed_at": datetime.now().isoformat(),
                    "dry_run": True,
                }
                continue

            # 3b. Download PDF
            time.sleep(1.0)
            pdf_bytes = _download_pdf(pdf_url)
            if not pdf_bytes:
                results["errors"].append({"title": title, "reason": "PDF download failed"})
                continue

            # Save a local copy
            pdf_filename = re.sub(r"[^a-zA-Z0-9_\-]", "_", title[:60]) + ".pdf"
            pdf_path = PDF_CACHE_DIR / pdf_filename
            pdf_path.write_bytes(pdf_bytes)

            # 3c. Extract text
            text = _extract_text_from_pdf(pdf_bytes)
            if len(text) < 100:
                results["errors"].append({"title": title, "reason": "PDF text too short after extraction"})
                continue

            # 3d. Build circular_id and process
            circular_id = _make_circular_id(title, date_str)
            pages = max(1, len(text) // 3000)

            logger.info(f"Ingesting circular_id={circular_id}, text_len={len(text)}, pages≈{pages}")

            pipeline_result = orchestrator.process_circular(
                circular_text=text,
                circular_id=circular_id,
                circular_title=title,
                intermediary_types=intermediary_types,
                pages=pages,
            )

            n_extracted = len(pipeline_result.get("extracted_obligations", []))
            n_new       = len(pipeline_result.get("diff_result", {}).get("new_obligations", []) if hasattr(pipeline_result.get("diff_result"), "__len__") else [])

            results["ingested"].append({
                "circular_id":     circular_id,
                "title":           title,
                "date":            date_str,
                "type":            ctype,
                "pdf_url":         pdf_url,
                "text_length":     len(text),
                "obligations_extracted": n_extracted,
                "processed_at":    datetime.now().isoformat(),
            })

            # 3e. Mark as seen
            seen[detail_url] = {
                "title":         title,
                "date":          date_str,
                "type":          ctype,
                "circular_id":   circular_id,
                "pdf_url":       pdf_url,
                "processed_at":  datetime.now().isoformat(),
            }
            _save_seen(seen)
            logger.info(f"✓ Ingested: {title[:60]} — {n_extracted} obligations")

        except Exception as e:
            logger.error(f"Error processing {title[:60]}: {e}")
            results["errors"].append({"title": title, "reason": str(e)})

    results["finished_at"] = datetime.now().isoformat()
    results["message"] = (
        f"Ingested {len(results['ingested'])} new circular(s), "
        f"{len(results['errors'])} error(s)."
    )

    _save_status({
        "last_run":  run_start.isoformat(),
        "status":    "ok" if not results["errors"] else "ok_with_errors",
        "ingested":  len(results["ingested"]),
        "errors":    len(results["errors"]),
        "details":   results,
    })

    return results
