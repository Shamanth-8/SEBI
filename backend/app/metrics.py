"""
Performance metrics for RegGraph pipeline.
Tracks extraction accuracy, processing time, and gap detection stats.
"""
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

METRICS_PATH = os.getenv("METRICS_PATH", "./data/metrics.json")


def _load() -> list:
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    if os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save(records: list) -> None:
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(records, f, indent=2, default=str)


@contextmanager
def timer():
    """Context manager — yields a dict; sets dict['seconds'] on exit."""
    result = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = round(time.perf_counter() - start, 3)


def record_pipeline_run(
    circular_id: str,
    circular_title: str,
    pages: int,
    text_length: int,
    chunks_processed: int,
    extraction_seconds: float,
    obligations_extracted: int,
    diff_seconds: float,
    new_count: int,
    modified_count: int,
    superseded_count: int,
    impact_seconds: float,
    affected_obligations: int,
    mapping_seconds: float,
    intermediary_types: List[str],
    evidence_gaps: int,
    total_seconds: float,
    impact_score: float,
    risk_level: str,
) -> Dict:
    record = {
        "timestamp": datetime.now().isoformat(),
        "circular_id": circular_id,
        "circular_title": circular_title,
        "input": {
            "pages": pages,
            "text_length": text_length,
            "chunks_processed": chunks_processed,
        },
        "extraction": {
            "seconds": extraction_seconds,
            "obligations_extracted": obligations_extracted,
            "obligations_per_page": round(obligations_extracted / max(pages, 1), 2),
        },
        "diff": {
            "seconds": diff_seconds,
            "new": new_count,
            "modified": modified_count,
            "superseded": superseded_count,
        },
        "impact": {
            "seconds": impact_seconds,
            "affected_obligations": affected_obligations,
        },
        "mapping": {
            "seconds": mapping_seconds,
            "intermediary_types": intermediary_types,
            "evidence_gaps": evidence_gaps,
        },
        "overall": {
            "total_seconds": total_seconds,
            "impact_score": impact_score,
            "risk_level": risk_level,
        },
    }
    records = _load()
    records.append(record)
    _save(records)
    return record


def get_all_metrics() -> List[Dict]:
    return _load()


def get_latest_run(circular_id: Optional[str] = None) -> Optional[Dict]:
    records = _load()
    if circular_id:
        records = [r for r in records if r["circular_id"] == circular_id]
    return records[-1] if records else None


def format_summary(record: Dict) -> str:
    lines = [
        "=" * 60,
        "PIPELINE METRICS SUMMARY",
        "=" * 60,
        f"Circular  : {record['circular_title']}",
        f"Timestamp : {record['timestamp']}",
        f"Pages     : {record['input']['pages']}  |  Chars: {record['input']['text_length']:,}  |  Chunks: {record['input']['chunks_processed']}",
        "",
        f"[Extraction]  {record['extraction']['seconds']:.1f}s  ->  {record['extraction']['obligations_extracted']} obligations  ({record['extraction']['obligations_per_page']} / page)",
        f"[Diff]        {record['diff']['seconds']:.1f}s  ->  NEW={record['diff']['new']}  MODIFIED={record['diff']['modified']}  SUPERSEDED={record['diff']['superseded']}",
        f"[Impact]      {record['impact']['seconds']:.1f}s  ->  {record['impact']['affected_obligations']} affected obligations",
        f"[Mapping]     {record['mapping']['seconds']:.1f}s  ->  {record['mapping']['evidence_gaps']} evidence gaps  across {record['mapping']['intermediary_types']}",
        "",
        f"Total time  : {record['overall']['total_seconds']:.1f}s",
        f"Impact score: {record['overall']['impact_score']:.2f}",
        f"Risk level  : {record['overall']['risk_level'].upper()}",
        "=" * 60,
    ]
    return "\n".join(lines)
