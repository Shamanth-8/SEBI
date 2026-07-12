#!/usr/bin/env python3
"""
Extract text from circular.pdf and prepare for processing.
"""
import pdfplumber
import json
from datetime import datetime

pdf_path = "circular.pdf"
output_path = "circular_extracted.json"

print(f"Extracting text from {pdf_path}...")

with pdfplumber.open(pdf_path) as pdf:
    pages = len(pdf.pages)
    text = ""
    
    for i, page in enumerate(pdf.pages, 1):
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n\n"
        print(f"  Processed page {i}/{pages}")

# Save to JSON
circular_data = {
    "circular_id": "SEBI_SURVEILLANCE_MC_2026",
    "title": "Master Circular on Surveillance of Securities Market",
    "issue_date": "2023-03-23",
    "last_updated": "2026-05-15",
    "pages": pages,
    "text_length": len(text),
    "full_text": text,
    "extracted_at": datetime.now().isoformat(),
    "intermediary_types": ["stockbroker", "depository", "listed_company", "fiduciary"]
}

with open(output_path, "w") as f:
    json.dump(circular_data, f, indent=2)

print(f"\n✅ Extracted {len(text):,} characters from {pages} pages")
print(f"✅ Saved to {output_path}")
print(f"\nFirst 500 chars preview:")
print(text[:500])
