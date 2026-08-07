"""
RegGraph Dashboard — Full redesign (Tier 5)
Custom CSS design system + streamlit-option-menu nav + all Tier 1-4 features.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import httpx
import json
import re
import io
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

import intel_views

st.set_page_config(
    page_title="RegGraph — Agentic Compliance",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
# A full run has historically taken far longer than the old 600s client timeout,
# which made the browser give up while the backend was still working — visually
# indistinguishable from "nothing happened".
PIPELINE_TIMEOUT = float(os.getenv("PIPELINE_TIMEOUT", "3600"))

# ─────────────────────────────────────────────────────────────────────────────
# DESIGN SYSTEM — injected once at startup
# ─────────────────────────────────────────────────────────────────────────────
DESIGN_CSS = """
<style>
/* ── Custom properties ── */
:root {
  --bg:        #0B0F19;
  --surface:   #131826;
  --border:    #1E293B;
  --accent:    #7C3AED;
  --accent-lt: #A78BFA;
  --text:      #E2E8F0;
  --muted:     #64748B;
  --high:      #F87171;
  --medium:    #FBBF24;
  --low:       #34D399;
  --high-bg:   rgba(248,113,113,0.10);
  --med-bg:    rgba(251,191,36,0.10);
  --low-bg:    rgba(52,211,153,0.10);
  --ev-red:    #EF4444;
  --ev-yellow: #F59E0B;
  --ev-green:  #22C55E;
  --radius:    10px;
  --shadow:    0 2px 12px rgba(0,0,0,0.45);
}

/* ── Global reset ── */
html, body, [data-testid="stAppViewContainer"] {
  background-color: var(--bg) !important;
  color: var(--text) !important;
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}
[data-testid="stSidebar"] {
  background-color: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stHeader"] { background: transparent !important; }

/* ── Typography scale ── */
h1 { font-size: 1.75rem !important; font-weight: 700 !important; color: var(--accent-lt) !important; letter-spacing: -0.5px; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; color: var(--text) !important; margin-top: 1.5rem !important; }
h3 { font-size: 1.05rem !important; font-weight: 600 !important; color: var(--text) !important; }
p, li, td, th { font-size: 0.9rem !important; line-height: 1.6 !important; }
small, .muted { font-size: 0.78rem !important; color: var(--muted) !important; }

/* ── Cards ── */
.rg-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  box-shadow: var(--shadow);
  margin-bottom: 16px;
}
.rg-card:hover { border-color: var(--accent); }

/* ── KPI metrics ── */
.kpi-row { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
.kpi-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 24px;
  min-width: 150px;
  flex: 1;
  box-shadow: var(--shadow);
}
.kpi-card.accent { border-color: var(--accent); }
.kpi-val { font-size: 2.1rem; font-weight: 700; color: var(--accent-lt); }
.kpi-val.high { color: var(--high); }
.kpi-val.green { color: var(--low); }
.kpi-lbl { font-size: 0.75rem; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.kpi-delta { font-size: 0.8rem; margin-top: 4px; }

/* ── Badges / pills ── */
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}
.badge-high   { background: var(--high-bg);  color: var(--high);   border: 1px solid rgba(248,113,113,0.30); }
.badge-medium { background: var(--med-bg);   color: var(--medium); border: 1px solid rgba(251,191,36,0.30); }
.badge-low    { background: var(--low-bg);   color: var(--low);    border: 1px solid rgba(52,211,153,0.30); }
.badge-red    { background: var(--high-bg);  color: var(--ev-red);    border: 1px solid rgba(239,68,68,0.30); }
.badge-yellow { background: var(--med-bg);   color: var(--ev-yellow); border: 1px solid rgba(245,158,11,0.30); }
.badge-green  { background: var(--low-bg);   color: var(--ev-green);  border: 1px solid rgba(34,197,94,0.30); }
.badge-critical { background: rgba(220,38,38,0.15); color: #FCA5A5; border: 1px solid rgba(220,38,38,0.35); }

/* ── Obligation cards ── */
.obl-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 12px;
  box-shadow: var(--shadow);
  position: relative;
}
.obl-card:hover { border-color: var(--accent-lt); }
.obl-title { font-weight: 600; font-size: 0.95rem; color: var(--text); margin-bottom: 4px; }
.obl-meta { font-size: 0.78rem; color: var(--muted); margin-top: 6px; display: flex; gap: 12px; flex-wrap: wrap; }
.obl-clause { font-size: 0.78rem; color: var(--muted); font-style: italic; margin-bottom: 8px; }

/* ── Progress bar ── */
.prog-bar-wrap { background: var(--border); border-radius: 4px; height: 6px; overflow: hidden; margin: 6px 0; }
.prog-bar-fill { height: 100%; border-radius: 4px; background: var(--accent); }
.prog-bar-fill.green { background: var(--ev-green); }
.prog-bar-fill.yellow { background: var(--ev-yellow); }
.prog-bar-fill.red { background: var(--ev-red); }

/* ── Stepper ── */
.stepper { list-style: none; padding: 0; margin: 0; }
.step-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; }
.step-icon { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; flex-shrink: 0; font-weight: 700; }
.step-icon.done    { background: rgba(52,211,153,0.2); color: var(--low); border: 1px solid var(--low); }
.step-icon.active  { background: rgba(124,58,237,0.2); color: var(--accent-lt); border: 1px solid var(--accent); }
.step-icon.pending { background: var(--border); color: var(--muted); border: 1px solid var(--border); }
.step-body { flex: 1; }
.step-name  { font-weight: 600; font-size: 0.88rem; color: var(--text); }
.step-result { font-size: 0.78rem; color: var(--muted); margin-top: 2px; }

/* ── Benchmark table ── */
.bench-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.bench-table th { background: var(--border); color: var(--muted); padding: 8px 14px; text-align: left; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.5px; }
.bench-table td { padding: 10px 14px; border-bottom: 1px solid var(--border); font-size: 0.88rem; }
.bench-table tr:last-child td { font-weight: 700; color: var(--accent-lt); background: rgba(124,58,237,0.07); }
.bench-manual { color: var(--high); }
.bench-ai     { color: var(--low); }

/* ── Copilot summary card ── */
.copilot-card {
  background: linear-gradient(135deg, rgba(124,58,237,0.12), rgba(167,139,250,0.05));
  border: 1px solid rgba(124,58,237,0.35);
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: 20px;
}
.copilot-title { font-size: 1.05rem; font-weight: 700; color: var(--accent-lt); margin-bottom: 12px; }

/* ── Section divider ── */
.rg-divider { border: none; border-top: 1px solid var(--border); margin: 24px 0; }

/* ── Empty state ── */
.empty-state { text-align: center; padding: 48px 24px; color: var(--muted); }
.empty-icon  { font-size: 3rem; margin-bottom: 12px; }
.empty-text  { font-size: 0.9rem; }

/* ── Loading skeleton ── */
@keyframes shimmer { 0%{background-position:-400px 0} 100%{background-position:400px 0} }
.skeleton {
  background: linear-gradient(90deg, var(--surface) 25%, var(--border) 50%, var(--surface) 75%);
  background-size: 800px 100%;
  animation: shimmer 1.4s infinite;
  border-radius: 4px;
  height: 16px;
  margin: 6px 0;
}

/* ── Streamlit widget overrides ── */
div[data-testid="metric-container"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 14px 18px !important;
}
div[data-testid="metric-container"] label { color: var(--muted) !important; font-size: 0.75rem !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: var(--accent-lt) !important; font-size: 1.6rem !important; font-weight: 700 !important; }

button[kind="primary"], .stButton > button[kind="primary"] {
  background: var(--accent) !important;
  border: none !important;
  border-radius: 8px !important;
  color: white !important;
  font-weight: 600 !important;
}
button[kind="primary"]:hover { background: #6D28D9 !important; }

.stTextInput > div > div > input,
.stSelectbox > div > div > div,
.stMultiSelect > div > div > div {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  color: var(--text) !important;
}
[data-testid="stExpander"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
}

/* ── Sidebar header ── */
.sidebar-brand { padding: 16px 0 8px 0; }
.sidebar-logo  { font-size: 1.3rem; font-weight: 800; color: var(--accent-lt); }
.sidebar-tag   { font-size: 0.75rem; color: var(--muted); margin-top: 2px; }

/* ══════════════════════════════════════════════════════════
   ANIMATIONS
   ══════════════════════════════════════════════════════════ */

/* Slide-in from bottom — used for cards appearing after pipeline */
@keyframes slideUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
.anim-slide-up {
  animation: slideUp 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* Fade in */
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
.anim-fade-in { animation: fadeIn 0.5s ease both; }

/* Success flash — green pulse on completion */
@keyframes successPulse {
  0%   { box-shadow: 0 0 0 0 rgba(34,197,94,0.55); }
  60%  { box-shadow: 0 0 0 14px rgba(34,197,94,0); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}
.anim-success {
  animation: successPulse 1.1s ease 0.1s both;
  border-color: var(--ev-green) !important;
}

/* Alert pulse — red pulse for overdue items */
@keyframes alertPulse {
  0%   { box-shadow: 0 0 0 0 rgba(239,68,68,0.5); }
  60%  { box-shadow: 0 0 0 10px rgba(239,68,68,0); }
  100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
}
.anim-alert { animation: alertPulse 1.4s ease infinite; }

/* Spinning loader */
@keyframes spin {
  to { transform: rotate(360deg); }
}
.spinner {
  display: inline-block;
  width: 18px; height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-lt);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}

/* KPI counter count-up shimmer */
@keyframes countUp {
  from { opacity: 0; transform: scale(0.8); }
  to   { opacity: 1; transform: scale(1); }
}
.kpi-val { animation: countUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both; }

/* Step item stagger */
.step-item:nth-child(1) { animation: slideUp 0.3s 0.0s both; }
.step-item:nth-child(2) { animation: slideUp 0.3s 0.05s both; }
.step-item:nth-child(3) { animation: slideUp 0.3s 0.10s both; }
.step-item:nth-child(4) { animation: slideUp 0.3s 0.15s both; }
.step-item:nth-child(5) { animation: slideUp 0.3s 0.20s both; }
.step-item:nth-child(6) { animation: slideUp 0.3s 0.25s both; }

/* Evidence requirement rows */
@keyframes rowPop {
  from { opacity: 0; transform: translateX(-10px); }
  to   { opacity: 1; transform: translateX(0); }
}
.ev-req-row {
  animation: rowPop 0.35s ease both;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  margin-bottom: 8px;
  background: var(--surface);
}
.ev-req-row:nth-child(1) { animation-delay: 0.0s; }
.ev-req-row:nth-child(2) { animation-delay: 0.05s; }
.ev-req-row:nth-child(3) { animation-delay: 0.10s; }
.ev-req-row:nth-child(4) { animation-delay: 0.15s; }
.ev-req-row:nth-child(5) { animation-delay: 0.20s; }
.ev-req-row.satisfied  { border-color: rgba(34,197,94,0.4); background: rgba(34,197,94,0.05); }
.ev-req-row.unsatisfied{ border-color: rgba(239,68,68,0.35); background: rgba(239,68,68,0.05); }

/* SOP step list */
.sop-step {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 8px 0;
  animation: slideUp 0.3s ease both;
}
.sop-step:nth-child(1) { animation-delay: 0.00s; }
.sop-step:nth-child(2) { animation-delay: 0.04s; }
.sop-step:nth-child(3) { animation-delay: 0.08s; }
.sop-step:nth-child(4) { animation-delay: 0.12s; }
.sop-step:nth-child(5) { animation-delay: 0.16s; }
.sop-step:nth-child(6) { animation-delay: 0.20s; }
.sop-num {
  min-width: 26px; height: 26px; border-radius: 50%;
  background: rgba(124,58,237,0.18); border: 1px solid rgba(124,58,237,0.4);
  color: var(--accent-lt); font-size: 0.75rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.sop-text { font-size: 0.87rem; color: var(--text); line-height: 1.55; }

/* LLM badge */
.llm-badge {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(124,58,237,0.15); border: 1px solid rgba(124,58,237,0.35);
  border-radius: 20px; padding: 2px 10px;
  font-size: 0.72rem; font-weight: 600; color: var(--accent-lt);
  letter-spacing: 0.3px;
}
.keyword-badge {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(100,116,139,0.15); border: 1px solid rgba(100,116,139,0.3);
  border-radius: 20px; padding: 2px 10px;
  font-size: 0.72rem; color: var(--muted);
}
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────────────────────────────────────

def api_get(endpoint: str, timeout: float = 15.0) -> Dict:
    try:
        r = httpx.get(f"{API_BASE_URL}{endpoint}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

def api_post(endpoint: str, payload: Dict, timeout: float = 600.0) -> Dict:
    try:
        r = httpx.post(f"{API_BASE_URL}{endpoint}", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

def has_error(data: Dict) -> bool:
    return "_error" in data or "error" in data

def sev_badge(sev: str) -> str:
    cls = {"high": "badge-high", "medium": "badge-medium", "low": "badge-low"}.get(sev, "badge-medium")
    return f'<span class="badge {cls}">{sev}</span>'

def ev_badge(ev: str) -> str:
    cls = {"green": "badge-green", "yellow": "badge-yellow", "red": "badge-red"}.get(ev, "badge-red")
    label = {"green": "✓ Complete", "yellow": "~ Partial", "red": "✗ Missing"}.get(ev, ev)
    return f'<span class="badge {cls}">{label}</span>'

def priority_badge(p: str) -> str:
    cls = {"critical": "badge-critical", "high": "badge-high", "medium": "badge-medium", "low": "badge-low"}.get(p, "badge-medium")
    return f'<span class="badge {cls}">{p}</span>'

def risk_color(score: float) -> str:
    if score >= 66: return "var(--high)"
    if score >= 31: return "var(--medium)"
    return "var(--low)"

def progress_bar(pct: float, color: str = "") -> str:
    c = color or ("green" if pct >= 75 else "yellow" if pct >= 40 else "red")
    return f"""<div class="prog-bar-wrap"><div class="prog-bar-fill {c}" style="width:{pct:.0f}%"></div></div>"""


def render_sop_steps(steps: list, generated_by: str = "template") -> str:
    """Render animated SOP step list with numbered circles."""
    badge = (
        '<span class="llm-badge">✦ LLM Generated</span>'
        if generated_by == "llm"
        else '<span class="keyword-badge">⚙ Template</span>'
    )
    rows = ""
    for i, step in enumerate(steps, 1):
        # Strip "Step N —" prefix if present so we don't double-display
        text = re.sub(r"^Step\s+\d+\s*[—\-:]\s*", "", str(step)).strip()
        rows += f"""
        <div class="sop-step">
          <div class="sop-num">{i}</div>
          <div class="sop-text">{text}</div>
        </div>"""
    return f"""
<div class="anim-slide-up" style="margin-top:8px">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
    <span style="font-size:0.82rem;font-weight:600;color:var(--text)">Standard Operating Procedure</span>
    {badge}
  </div>
  {rows}
</div>"""


def render_evidence_reasoning(per_requirement: list, overall_reasoning: str, method: str) -> str:
    """Render per-requirement evidence match results with animated rows."""
    method_badge = (
        '<span class="llm-badge">✦ Semantic Match</span>'
        if method == "llm"
        else '<span class="keyword-badge">⚙ Keyword Match</span>'
    )
    rows = ""
    for req in per_requirement:
        satisfied = req.get("satisfied", False)
        score     = req.get("score", 0.0)
        reasoning = req.get("reasoning", "")
        req_text  = req.get("requirement", "")
        icon      = "✅" if satisfied else "❌"
        cls       = "satisfied" if satisfied else "unsatisfied"
        score_pct = int(score * 100)
        score_color = "var(--ev-green)" if score >= 0.7 else "var(--ev-yellow)" if score >= 0.4 else "var(--ev-red)"
        rows += f"""
        <div class="ev-req-row {cls}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
            <span style="font-size:0.85rem;font-weight:600">{icon} {req_text}</span>
            <span style="font-size:0.78rem;font-weight:700;color:{score_color};white-space:nowrap">{score_pct}%</span>
          </div>
          <div style="font-size:0.78rem;color:var(--muted);margin-top:4px">{reasoning}</div>
        </div>"""

    overall_html = ""
    if overall_reasoning:
        overall_html = f"""
      <div style="margin-top:12px;padding:10px 14px;background:rgba(124,58,237,0.07);
                  border-radius:8px;border:1px solid rgba(124,58,237,0.2)">
        <span style="font-size:0.75rem;color:var(--accent-lt);font-weight:600">OVERALL ASSESSMENT</span><br>
        <span style="font-size:0.82rem;color:var(--muted)">{overall_reasoning}</span>
      </div>"""

    return f"""
<div class="anim-fade-in" style="margin-top:10px">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
    <span style="font-size:0.82rem;font-weight:600;color:var(--text)">Evidence Analysis</span>
    {method_badge}
  </div>
  {rows}
  {overall_html}
</div>"""

def _extract_pdf_text(file_bytes: bytes) -> str:
    import pdfplumber
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text

def _parse_metadata(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    ref_re = re.compile(
        r'(?:SEBI[/\s])?(?:HO|CIR|ISD|MIRSD|IMD|OIAE|MRD|CFD|ERO)[/\-][A-Z0-9/\-\(\)\.]{5,60}',
        re.IGNORECASE
    )
    circular_id = ""
    for line in lines[:15]:
        m = ref_re.search(line)
        if m:
            raw = m.group(0).strip()
            circular_id = re.sub(r'[^A-Za-z0-9_\-]', '_', raw)[:60]
            break
    if not circular_id:
        circular_id = f"SEBI_CIRCULAR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    title = ""
    subj_re = re.compile(r'^(sub|subject|re)\s*[:\-]\s*(.+)', re.IGNORECASE)
    for line in lines[:25]:
        m = subj_re.match(line)
        if m:
            title = m.group(2).strip()
            break
    if not title:
        # Fall back to the first substantive line, skipping short/ALL-CAPS
        # letterhead or logo lines that don't carry the actual title.
        for line in lines[1:25]:
            if len(line) >= 15 and not line.isupper():
                title = line
                break
    if not title and len(lines) > 1:
        title = lines[1]
    return circular_id, title



# ─────────────────────────────────────────────────────────────────────────────
# PAGE: UPLOAD + PIPELINE STEPPER
# ─────────────────────────────────────────────────────────────────────────────

PIPELINE_STEPS = [
    ("📄", "Extraction Agent",           "Reads circular chunks, identifies obligations"),
    ("⚖️",  "Legal Interpretation Agent", "Detects mandatory language: shall / must / required"),
    ("🔍", "Semantic Diff Agent",        "Classifies NEW / MODIFIED / SUPERSEDED vs graph"),
    ("🌐", "Impact Analysis Agent",      "BFS traversal — finds all downstream dependencies"),
    ("📋", "Compliance Planning Agent",  "Maps obligations, generates tasks & SOPs"),
    ("🔒", "Audit Agent",                "Timestamps every step, saves graph & metrics"),
]

def _render_stepper(done: int, results: list[str], error: str = "") -> str:
    html = '<ul class="stepper">'
    for i, (icon, name, desc) in enumerate(PIPELINE_STEPS):
        if i < done:
            state = "done"; icon_txt = "✓"
            result_txt = results[i] if i < len(results) else "Complete"
        elif i == done and not error:
            state = "active"; icon_txt = "…"
            result_txt = desc
        else:
            state = "pending"; icon_txt = str(i + 1)
            result_txt = desc
        html += f"""
        <li class="step-item">
          <div class="step-icon {state}">{icon_txt}</div>
          <div class="step-body">
            <div class="step-name">{icon} {name}</div>
            <div class="step-result">{result_txt}</div>
          </div>
        </li>"""
    if error:
        html += f'<li style="color:var(--high);padding:8px 0;font-size:0.85rem">❌ Error: {error[:200]}</li>'
    html += "</ul>"
    return html


def show_upload_page():
    st.markdown("## 📤 Upload Regulatory Circular")
    st.markdown(
        '<p class="muted">Drop a SEBI circular PDF → the multi-agent pipeline extracts, '
        'diffs, and maps obligations automatically.</p>', unsafe_allow_html=True
    )

    # ── Show last pipeline result if returning to this page ───────────────
    if "last_pipeline" in st.session_state:
        p = st.session_state["last_pipeline"]
        st.markdown(f"""
<div class="rg-card anim-fade-in" style="border-color:var(--accent);margin-bottom:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
    <div>
      <span style="font-size:0.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px">Previous Run (not the file below)</span><br>
      <span style="font-weight:600;color:var(--accent-lt)">{p.get("circular_title","—")[:70]}</span>
      <span style="font-size:0.78rem;color:var(--muted);margin-left:8px">{p.get("circular_id","—")[:45]} · {p.get("ran_at","")}</span>
    </div>
    <div style="display:flex;gap:16px;font-size:0.85rem">
      <span>📋 <b style="color:var(--accent-lt)">{p.get("n_extracted",0)}</b> extracted</span>
      <span>🆕 <b style="color:var(--accent-lt)">{p.get("n_new",0)}</b> new</span>
      <span>✏️ <b style="color:var(--medium)">{p.get("n_mod",0)}</b> modified</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
        with st.expander("📊 View full last run results"):
            _show_pipeline_result(p, nested=True)
        st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Drop circular PDF here", type=["pdf", "txt"])

    # ── Persist file content in session_state across Streamlit rerenders ──
    # Use file name+size as a cache key so uploading a different file always
    # overwrites the previous cache, even if the widget returns None on rerender.
    if uploaded_file is not None:
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("upload_file_key") != file_key:
            # Genuinely new file — read, extract, cache
            raw = uploaded_file.read()
            fname = uploaded_file.name or ""
            read_error = ""
            with st.spinner("Reading file…"):
                if fname.lower().endswith(".pdf"):
                    # Must not be unguarded: an encrypted or malformed PDF used to
                    # raise here and kill the whole page before the uploader, the
                    # metadata fields and the Run button were ever rendered.
                    try:
                        text = _extract_pdf_text(raw)
                    except Exception as exc:
                        text = ""
                        read_error = f"Could not read this PDF: {exc}"
                else:
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = raw.decode("latin-1")
            auto_id, auto_title = _parse_metadata(text)
            st.session_state["upload_file_key"]    = file_key
            st.session_state["upload_file_bytes"]  = raw
            st.session_state["upload_doc_text"]    = text
            st.session_state["upload_filename"]    = fname
            st.session_state["upload_auto_id"]     = auto_id
            st.session_state["upload_auto_title"]  = auto_title
            st.session_state["upload_read_error"]  = read_error
            # Point the editable fields at the NEW file's metadata, and drop the
            # previous run's result card so stale numbers can't look current.
            st.session_state["circular_id_input"]    = auto_id
            st.session_state["circular_title_input"] = auto_title
            st.session_state.pop("last_pipeline", None)
            st.rerun()

        read_error = st.session_state.get("upload_read_error", "")
        cached_text = st.session_state.get("upload_doc_text", "")
        if read_error:
            st.error(f"❌ {read_error}")
            st.caption("If the PDF is password-protected, remove the protection and re-upload, "
                       "or paste the text manually below.")
        elif not cached_text.strip():
            st.error(
                f"❌ No text layer found in `{st.session_state.get('upload_filename','')}` — "
                "this looks like a scanned/image PDF, so there is nothing to extract."
            )
            st.caption("Run it through OCR first, or paste the circular text manually below.")
        else:
            st.success(f"✅ Read **{len(cached_text):,} characters** from `{st.session_state['upload_filename']}`")

    # Restore from cache (survives rerenders from widget interactions)
    file_bytes = st.session_state.get("upload_file_bytes", b"")
    doc_text   = st.session_state.get("upload_doc_text",   "")
    filename   = st.session_state.get("upload_filename",   "")
    auto_id    = st.session_state.get("upload_auto_id",    "")
    auto_title = st.session_state.get("upload_auto_title", "")

    # Show the paste fallback whenever we have no usable text — including when a
    # file was uploaded but yielded nothing (scanned PDF / unreadable file).
    if not doc_text.strip():
        pasted = st.text_area("Or paste circular text", height=120,
                              placeholder="Paste full circular text here…",
                              value=doc_text)
        if pasted.strip():
            doc_text = pasted
            auto_id, auto_title = _parse_metadata(doc_text)
            st.session_state["upload_doc_text"]   = doc_text
            st.session_state["upload_auto_id"]    = auto_id
            st.session_state["upload_auto_title"] = auto_title
            st.session_state.setdefault("circular_id_input", auto_id)
            st.session_state.setdefault("circular_title_input", auto_title)
    elif uploaded_file is None and file_bytes:
        st.info(f"📄 Using cached: `{filename}` ({len(doc_text):,} chars) — ready to run.")

    # Keyed widgets: without an explicit key these did not reliably refresh when a
    # new file replaced a cached one, so the fields kept showing the old circular.
    st.session_state.setdefault("circular_id_input", auto_id)
    st.session_state.setdefault("circular_title_input", auto_title)

    col1, col2 = st.columns(2)
    with col1:
        circular_id = st.text_input("Circular ID", key="circular_id_input")
    with col2:
        circular_title = st.text_input("Title", key="circular_title_input")

    intermediary_types = st.multiselect(
        "Intermediary types",
        ["stockbroker", "depository", "listed_company", "investment_adviser", "fiduciary", "rta"],
        default=["stockbroker", "depository", "listed_company"],
    )

    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    can_run = bool(doc_text.strip()) and bool(circular_id.strip())

    col_run, col_clear = st.columns([4, 1])
    with col_run:
        if st.button("🚀 Run Agent Pipeline", type="primary", disabled=not can_run, use_container_width=True):
            _run_pipeline(circular_id, circular_title, doc_text, file_bytes, filename, intermediary_types)
    with col_clear:
        if st.button("🗑 Clear", use_container_width=True, disabled=not (file_bytes or doc_text)):
            for k in ["upload_file_bytes", "upload_doc_text", "upload_filename",
                      "upload_auto_id", "upload_auto_title", "upload_file_key",
                      "upload_read_error", "circular_id_input", "circular_title_input",
                      "last_pipeline"]:
                st.session_state.pop(k, None)
            st.rerun()

    # Say *why* the button is disabled instead of leaving it silently greyed out.
    if not can_run:
        missing = []
        if not doc_text.strip():
            missing.append("circular text (upload a text-based PDF/TXT or paste it above)")
        if not circular_id.strip():
            missing.append("a Circular ID")
        st.caption(f"⚠️ Run is disabled — still needs: {', '.join(missing)}.")


def _run_pipeline(circular_id, circular_title, doc_text, file_bytes, filename, intermediary_types):
    stat_slot  = st.empty()
    step_slot  = st.empty()
    step_results = [""] * len(PIPELINE_STEPS)

    def render(done: int, error: str = ""):
        step_slot.markdown(
            f'<div class="rg-card">{_render_stepper(done, step_results, error)}</div>',
            unsafe_allow_html=True
        )

    stat_slot.markdown(
        '<div class="kpi-row">'
        '<div class="kpi-card"><div class="kpi-val">—</div><div class="kpi-lbl">Extracted</div></div>'
        '<div class="kpi-card"><div class="kpi-val">—</div><div class="kpi-lbl">NEW</div></div>'
        '<div class="kpi-card"><div class="kpi-val">—</div><div class="kpi-lbl">MODIFIED</div></div>'
        '<div class="kpi-card"><div class="kpi-val">—</div><div class="kpi-lbl">SUPERSEDED</div></div>'
        '</div>', unsafe_allow_html=True
    )
    render(0)

    try:
        if file_bytes and filename.lower().endswith(".pdf"):
            render(1); step_results[0] = "PDF extracted and chunked"
            resp = httpx.post(
                f"{API_BASE_URL}/circulars/upload-file",
                data={"circular_id": circular_id, "title": circular_title,
                      "intermediary_types": ",".join(intermediary_types)},
                files={"file": (filename, file_bytes, "application/pdf")},
                timeout=PIPELINE_TIMEOUT,
            )
        else:
            render(1); step_results[0] = "Text chunked into sections"
            resp = httpx.post(
                f"{API_BASE_URL}/circulars/upload",
                json={"circular_id": circular_id, "title": circular_title,
                      "document_text": doc_text, "intermediary_types": intermediary_types},
                timeout=PIPELINE_TIMEOUT,
            )

        if resp.status_code != 200:
            detail = resp.text[:500]
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            render(0, error=str(detail)[:300])
            if resp.status_code == 502:
                st.error(f"🔌 The language model could not be reached — nothing was extracted.\n\n{detail}")
                st.caption("Check `GET /api/v1/health/llm` for the exact cause "
                           "(wrong model id, bad key, or daily quota exhausted).")
            else:
                st.error(f"❌ Upload failed (HTTP {resp.status_code}): {detail}")
            return

        result      = resp.json()
        n_extracted = result.get("extracted_obligations_count", 0)
        n_new       = result.get("new_obligations_count", 0)
        n_mod       = result.get("modified_obligations_count", 0)
        n_sup       = result.get("superseded_obligations_count", 0)
        risk_level  = result.get("risk_level", "medium")
        chunks_failed = result.get("chunks_failed", 0)
        chunks_total  = result.get("chunks_total", 0)
        llm_error     = result.get("llm_error")

        # A run that extracted nothing is a failure to report, not a success to
        # celebrate — this used to render as a green "complete" with zeros.
        if chunks_failed:
            st.warning(
                f"⚠️ {chunks_failed} of {chunks_total} sections failed to process. "
                f"Results are incomplete.\n\nLast error: {llm_error}"
            )
        if n_extracted == 0:
            st.error(
                "❌ Zero obligations were extracted. "
                + (f"The model reported: {llm_error}" if llm_error
                   else "The model returned no obligations for this document.")
            )
            st.caption("Check `GET /api/v1/health/llm` to confirm the model is reachable.")

        step_results[1] = f"{n_extracted} obligations extracted"
        step_results[2] = f"NEW={n_new}  MODIFIED={n_mod}  SUPERSEDED={n_sup}"
        step_results[3] = "Impact propagation complete"
        step_results[4] = f"Action tasks generated for {', '.join(intermediary_types)}"
        step_results[5] = "Graph saved · audit logged · metrics recorded"
        render(6)

        stat_slot.markdown(
            f'<div class="kpi-row anim-slide-up">'
            f'<div class="kpi-card accent anim-success"><div class="kpi-val">{n_extracted}</div><div class="kpi-lbl">Extracted</div></div>'
            f'<div class="kpi-card"><div class="kpi-val" style="color:var(--accent-lt)">{n_new}</div><div class="kpi-lbl">NEW</div></div>'
            f'<div class="kpi-card"><div class="kpi-val" style="color:var(--medium)">{n_mod}</div><div class="kpi-lbl">MODIFIED</div></div>'
            f'<div class="kpi-card"><div class="kpi-val" style="color:var(--muted)">{n_sup}</div><div class="kpi-lbl">SUPERSEDED</div></div>'
            f'</div>', unsafe_allow_html=True
        )
        if n_extracted:
            st.toast(f"✅ Pipeline complete — {n_extracted} obligations, {n_new} new, {n_mod} modified", icon="🏛")

        # ── Save everything to session_state so it survives page navigation ──
        copilot = api_get("/copilot/summary", timeout=10)
        pre_ai  = api_get("/copilot/pre-ai", timeout=15)
        ai_ins  = api_get("/copilot/ai-insights", timeout=15)
        st.session_state["last_pipeline"] = {
            "pre_ai":  pre_ai if not has_error(pre_ai) else None,
            "ai_insights": ai_ins if not has_error(ai_ins) else None,
            "circular_id":        circular_id,
            "circular_title":     circular_title,
            "filename":           filename,
            "n_extracted":        n_extracted,
            "n_new":              n_new,
            "n_mod":              n_mod,
            "n_sup":              n_sup,
            "risk_level":         risk_level,
            "intermediary_types": intermediary_types,
            "copilot":            copilot if not has_error(copilot) else None,
            "ran_at":             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
        _show_pipeline_result(st.session_state["last_pipeline"])

    except httpx.TimeoutException:
        render(0, error=f"Timed out after {PIPELINE_TIMEOUT:.0f}s")
        st.error(
            f"⏱ The backend did not respond within {PIPELINE_TIMEOUT:.0f}s. "
            "It may still be processing — check the backend logs and "
            "`GET /api/v1/audit/trail` before re-running, so you don't double-process."
        )
    except Exception as exc:
        render(0, error=str(exc))
        st.error(f"❌ Pipeline failed: {exc}")


def _show_pipeline_result(p: dict, nested: bool = False):
    """Render pipeline result card — called both inline and on return to Upload page.

    nested=True when the caller has already opened an st.expander around this
    (Streamlit forbids nesting expanders), so the audit trail renders in a
    plain container instead of its own expander.
    """
    circular_id = p.get("circular_id", "")
    n_extracted = p.get("n_extracted", 0)
    risk_level  = p.get("risk_level", "medium")
    copilot     = p.get("copilot")
    ran_at      = p.get("ran_at", "")

    st.markdown(f"### 🤖 Last Pipeline Run — {p.get('circular_title','—')} <span style='font-size:0.75rem;color:var(--muted);font-weight:400'>{ran_at}</span>", unsafe_allow_html=True)

    # KPI row
    n_new = p.get("n_new", 0); n_mod = p.get("n_mod", 0); n_sup = p.get("n_sup", 0)
    risk_color = {"high":"var(--high)","medium":"var(--medium)","low":"var(--low)"}.get(risk_level,"var(--medium)")
    st.markdown(f"""
<div class="kpi-row anim-slide-up">
  <div class="kpi-card accent"><div class="kpi-val">{n_extracted}</div><div class="kpi-lbl">Obligations Extracted</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--accent-lt)">{n_new}</div><div class="kpi-lbl">NEW</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--medium)">{n_mod}</div><div class="kpi-lbl">MODIFIED</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--muted)">{n_sup}</div><div class="kpi-lbl">SUPERSEDED</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:{risk_color}">{risk_level.upper()}</div><div class="kpi-lbl">Risk Level</div></div>
</div>""", unsafe_allow_html=True)

    if copilot and copilot.get("summary"):
        s        = copilot["summary"]
        affected = ", ".join(copilot.get("affected_intermediaries", []))
        depts    = ", ".join(copilot.get("departments_impacted", []))
        effort   = copilot.get("effort_estimate", {})
        est_days = effort.get("estimated_implementation_days", "—")
        top3     = copilot.get("top_3_immediate_actions", [])
        actions_html = ""
        for a in top3:
            pb = priority_badge(a.get("priority", "medium"))
            days_txt = f"due in {a['days_remaining']}d" if a.get("days_remaining") is not None else a.get("due_date") or "—"
            actions_html += f'<li style="margin:4px 0;">{pb} <b>{a["title"]}</b> — <span style="color:var(--muted)">{a["department"]} · {days_txt}</span></li>'

        st.markdown(f"""
<div class="copilot-card anim-fade-in">
  <div class="copilot-title">📋 What changed? What to do next?</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;flex-wrap:wrap">
    <div>
      <p style="color:var(--muted);font-size:0.78rem;margin-bottom:4px">AFFECTED INTERMEDIARIES</p>
      <p style="font-size:0.88rem">{affected or '—'}</p>
    </div>
    <div>
      <p style="color:var(--muted);font-size:0.78rem;margin-bottom:4px">DEPARTMENTS IMPACTED</p>
      <p style="font-size:0.88rem">{depts or '—'}</p>
    </div>
    <div>
      <p style="color:var(--muted);font-size:0.78rem;margin-bottom:4px">TASKS CREATED</p>
      <p style="font-size:1.4rem;font-weight:700;color:var(--accent-lt)">{s.get("total_tasks_created","—")}</p>
      <p style="color:var(--muted);font-size:0.75rem">Est. {est_days} days implementation</p>
    </div>
  </div>
  <p style="color:var(--muted);font-size:0.78rem;margin:12px 0 4px">TOP 3 IMMEDIATE ACTIONS</p>
  <ul style="padding-left:16px;margin:0">{actions_html}</ul>
</div>""", unsafe_allow_html=True)
    else:
        risk_icon = "🔴" if risk_level == "high" else "🟡" if risk_level == "medium" else "🟢"
        st.info(f"{risk_icon} Risk level: **{risk_level.upper()}** · {n_extracted} obligations extracted and saved to graph.")

    # ── Two-layer intelligence: local analysis first, then the AI layer ──────
    pre_ai = p.get("pre_ai")
    ai_ins = p.get("ai_insights")
    if pre_ai or ai_ins:
        tab_local, tab_ai = st.tabs([
            "🧠 Local analysis (no LLM)", "🤖 AI insights (LLM layer)",
        ])
        with tab_local:
            if pre_ai:
                st.caption("Computed by the trained model before any LLM call — same input "
                           "always gives the same output.")
                intel_views.render_pre_ai_block(pre_ai)
            else:
                st.info("No local analysis was recorded for this run.")
        with tab_ai:
            intel_views.render_ai_block(ai_ins or {})

    if nested:
        st.markdown("**🔒 Audit trail for this run**")
        audit_ctx = st.container()
    else:
        audit_ctx = st.expander("🔒 Audit trail for this run")
    with audit_ctx:
        ar = api_get(f"/audit/trail?circular_id={circular_id}", timeout=10)
        for e in ar.get("entries", []):
            ts  = e.get("timestamp","")[:19]
            evt = e.get("event_type","")
            ok  = "✅" if e.get("status") == "success" else "❌"
            st.markdown(f'`{ts}` {ok} **{evt}**')


def show_overview_page(intermediary_type: str):
    st.markdown("## 📈 Dashboard Overview")

    stats = api_get("/graph/statistics")
    if has_error(stats) or stats.get("total_obligations", 0) == 0:
        st.markdown("""
<div class="empty-state">
  <div class="empty-icon">📭</div>
  <div class="empty-text">No obligations yet — upload a circular first (📤 Upload Circular in the sidebar).</div>
</div>""", unsafe_allow_html=True)
        return

    # ── Benchmark headline (most prominent stat) ──────────────────────────
    bench = api_get("/audit/benchmark", timeout=10)
    if not has_error(bench):
        headline = bench.get("headline", "")
        tagline  = bench.get("tagline", "")
        st.markdown(f"""
<div class="rg-card" style="border-color:var(--accent);background:linear-gradient(135deg,rgba(124,58,237,0.10),rgba(11,15,25,1));">
  <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
    <div>
      <div style="font-size:2.6rem;font-weight:800;color:var(--accent-lt)">{headline}</div>
      <div style="font-size:1rem;color:var(--muted);margin-top:4px">{tagline}</div>
    </div>
    <div style="flex:1;text-align:right;">
      <span style="font-size:0.78rem;color:var(--muted)">vs manual compliance analyst process</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── KPI row ────────────────────────────────────────────────────────────
    scores = api_get(f"/compliance/score/{intermediary_type}", timeout=10)
    score_val = scores.get("compliance_score", 0.0) if not has_error(scores) else 0.0

    ev = stats.get("evidence_gaps", {})
    total_obs = stats.get("total_obligations", 0)
    ev_pct = round(ev.get("complete", 0) / max(total_obs, 1) * 100, 1)

    st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card accent">
    <div class="kpi-val">{score_val:.0f}%</div>
    <div class="kpi-lbl">Compliance Score ({intermediary_type.replace("_"," ").title()})</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{total_obs}</div>
    <div class="kpi-lbl">Total Obligations</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val high">{stats.get("high_severity_count",0)}</div>
    <div class="kpi-lbl">High Severity</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val green">{ev_pct:.0f}%</div>
    <div class="kpi-lbl">Evidence Complete</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{stats.get("circulars_ingested",0)}</div>
    <div class="kpi-lbl">Circulars Ingested</div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Charts row ────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        # Evidence status bar chart
        fig = go.Figure(go.Bar(
            x=["Complete", "Partial", "Missing"],
            y=[ev.get("complete", 0), ev.get("partial", 0), ev.get("missing", 0)],
            marker_color=["#22C55E", "#F59E0B", "#EF4444"],
            marker_line_width=0,
        ))
        fig.update_layout(
            title="Evidence Status",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#94A3B8", font_size=12,
            margin=dict(l=8, r=8, t=40, b=8),
            xaxis=dict(gridcolor="#1E293B"), yaxis=dict(gridcolor="#1E293B"),
            height=240,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Per-intermediary compliance scores
        all_scores_data = api_get("/compliance/score", timeout=10)
        all_scores = all_scores_data.get("scores", {}) if not has_error(all_scores_data) else {}
        all_scores.pop("overall", None)
        if all_scores:
            fig2 = go.Figure(go.Bar(
                x=list(all_scores.values()),
                y=[k.replace("_", " ").title() for k in all_scores.keys()],
                orientation="h",
                marker=dict(
                    color=list(all_scores.values()),
                    colorscale=[[0, "#EF4444"], [0.5, "#F59E0B"], [1, "#22C55E"]],
                    cmin=0, cmax=100,
                ),
            ))
            fig2.update_layout(
                title="Compliance Score by Intermediary",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#94A3B8", font_size=12,
                xaxis=dict(range=[0,100], gridcolor="#1E293B"),
                yaxis=dict(gridcolor="#1E293B"),
                margin=dict(l=8, r=8, t=40, b=8),
                height=240,
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── Benchmark table ────────────────────────────────────────────────────
    if not has_error(bench):
        st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
        st.markdown("### ⏱ Manual vs RegGraph — Time Comparison")
        rows_html = ""
        for row in bench.get("benchmark_rows", []):
            is_total = row["task"] == "TOTAL"
            style = 'style="font-weight:700;background:rgba(124,58,237,0.07)"' if is_total else ""
            rows_html += f"""<tr {style}>
              <td>{row["task"]}</td>
              <td class="bench-manual">{row["manual"]}</td>
              <td class="bench-ai">{row["regraph"]}</td>
            </tr>"""
        st.markdown(f"""
<table class="bench-table">
  <thead><tr><th>Task</th><th>Manual (assumed)</th><th>RegGraph (measured)</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)

    # ── Latest pipeline metrics ────────────────────────────────────────────
    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    metrics = api_get("/audit/metrics/latest", timeout=10)
    if not has_error(metrics) and metrics.get("data"):
        d = metrics["data"]
        st.markdown("### 🔬 Latest Pipeline Metrics")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Extraction time", f"{d['extraction']['seconds']:.1f}s")
        mc2.metric("Obligations/page", d['extraction']['obligations_per_page'])
        mc3.metric("Diff time",        f"{d['diff']['seconds']:.1f}s")
        mc4.metric("Total pipeline",   f"{d['overall']['total_seconds']:.1f}s")



# ─────────────────────────────────────────────────────────────────────────────
# PAGE: OBLIGATIONS + URGENCY QUEUE
# ─────────────────────────────────────────────────────────────────────────────

def show_obligations_page(intermediary_type: str):
    st.markdown("## 📋 Obligations & Risk Queue")

    tab1, tab2 = st.tabs(["🚨 Urgency Queue (by Risk)", "🔍 Search Obligations"])

    with tab1:
        _show_urgency_queue(intermediary_type)

    with tab2:
        _show_search_obligations(intermediary_type)


def _show_urgency_queue(intermediary_type: str):
    data = api_get(f"/obligations/urgency?intermediary_type={intermediary_type}&limit=50")
    if has_error(data) or not data.get("queue"):
        st.markdown('<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">No obligations yet. Upload a circular first.</div></div>', unsafe_allow_html=True)
        return

    queue = data["queue"]
    overdue = [q for q in queue if q.get("overdue")]
    critical_n = sum(1 for q in queue if q.get("risk_label") == "High")

    st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card"><div class="kpi-val">{len(queue)}</div><div class="kpi-lbl">Total</div></div>
  <div class="kpi-card"><div class="kpi-val high">{len(overdue)}</div><div class="kpi-lbl">Overdue</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--high)">{critical_n}</div><div class="kpi-lbl">High Risk</div></div>
</div>""", unsafe_allow_html=True)

    for item in queue[:20]:
        score = item.get("risk_score", 0)
        label = item.get("risk_label", "Low")
        days  = item.get("days_remaining")
        ev    = item.get("evidence_status", "red")

        if days is not None and days < 0:
            days_str = f'<span style="color:var(--high);font-weight:600">⚠ {abs(days)}d overdue</span>'
        elif days is not None:
            days_str = f'<span style="color:var(--medium)">{days}d remaining</span>'
        else:
            days_str = '<span style="color:var(--muted)">No deadline</span>'

        with st.expander(f"{'🔴' if label=='High' else '🟡' if label=='Medium' else '🟢'} {item['title']} — Risk {score:.0f}/100"):
            st.markdown(f"""
<div class="obl-card" style="margin:0">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
    <div>
      {sev_badge(item.get("severity","medium"))} {ev_badge(ev)}
      &nbsp;<span class="badge" style="background:rgba(124,58,237,0.15);color:var(--accent-lt);border:1px solid rgba(124,58,237,0.3)">Risk {score:.0f} · {label}</span>
    </div>
    <div>{days_str}</div>
  </div>
  <div class="obl-meta" style="margin-top:10px">
    <span>🏢 {item.get("responsible_party","—")}</span>
    <span>📅 {item.get("deadline") or "No deadline"}</span>
    <span>🏦 {", ".join(item.get("intermediary_types",[]))}</span>
  </div>
  <div style="margin-top:10px">
    <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--muted);margin-bottom:4px">
      <span>Risk score</span><span>{score:.0f}/100</span>
    </div>
    {progress_bar(score, "red" if score>=66 else "yellow" if score>=31 else "green")}
  </div>
</div>""", unsafe_allow_html=True)

            # Explainability sub-section
            expl = api_get(f"/obligations/{item['obligation_id']}/explainability", timeout=5)
            if not has_error(expl):
                st.markdown(f"""
<div style="margin-top:10px;padding:10px 14px;background:rgba(124,58,237,0.07);border-radius:8px;border:1px solid rgba(124,58,237,0.2)">
  <span style="font-size:0.75rem;color:var(--accent-lt);font-weight:600">WHY EXTRACTED</span><br>
  <span style="font-size:0.82rem;color:var(--muted)">{expl.get("extraction_rationale","—")}</span>
  &nbsp;&nbsp;<span style="font-size:0.75rem">Confidence: <b style="color:var(--accent-lt)">{expl.get("confidence_score",0.8)*100:.0f}%</b></span>
  &nbsp;&nbsp;Keywords: <b style="color:var(--medium)">{", ".join(expl.get("mandatory_keywords",[])[:4]) or "—"}</b>
</div>""", unsafe_allow_html=True)

            # SOP — fetch LLM version with intermediary context
            sop = api_get(f"/obligations/{item['obligation_id']}/sop?use_llm=true&intermediary_type={intermediary_type}", timeout=15)
            if not has_error(sop) and sop.get("sop_steps"):
                st.markdown(
                    render_sop_steps(sop["sop_steps"], sop.get("generated_by", "template")),
                    unsafe_allow_html=True,
                )

            # Checklist progress
            chk = api_get(f"/evidence/checklist/{item['obligation_id']}", timeout=5)
            if not has_error(chk) and chk.get("checklist"):
                pct = chk.get("completion_pct", 0)
                prog = chk.get("progress", "0/0")
                st.markdown(f"**Evidence checklist** ({prog} — {pct:.0f}% complete)")
                st.markdown(progress_bar(pct), unsafe_allow_html=True)
                for ci in chk["checklist"]:
                    icon = "✅" if ci["completed"] else "☐"
                    st.markdown(f"{icon} {ci['label']}")


def _show_search_obligations(intermediary_type: str):
    query = st.text_input("🔍 Search obligations", placeholder="e.g. trading window, margin, insider trading")
    if not query:
        return
    results = api_get(f"/obligations/search?query={query}&semantic=true")
    items = results.get("results", [])
    if not items:
        st.info("No results found.")
        return
    st.caption(f"Found {len(items)} obligations")
    for obl in items:
        with st.expander(f"📌 {obl['title']}"):
            st.markdown(f"""
<div class="obl-card" style="margin:0">
  {sev_badge(obl.get("severity","medium"))} {ev_badge(obl.get("evidence_status","red"))}
  <div class="obl-clause">{obl.get("clause_reference","—")}</div>
  <div style="font-size:0.88rem;color:var(--text)">{obl.get("description","")[:300]}</div>
  <div class="obl-meta">
    <span>🏢 {obl.get("responsible_party","—")}</span>
    <span>📅 {obl.get("deadline") or "No deadline"}</span>
    <span>🎯 {obl.get("required_action","")[:80]}</span>
  </div>
</div>""", unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────────────
# PAGE: GRAPH VISUALIZATION + ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

def show_graph_page():
    st.markdown("## 🌐 Obligation Graph — Digital Twin")
    st.markdown('<p class="muted">Every node is an obligation. Every edge is a dependency, supersession, or cross-reference. Node size = downstream impact.</p>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📊 Graph Analytics", "🗺 Interactive Graph", "🔗 Impact Analysis"])

    with tab1:
        _show_graph_analytics()
    with tab2:
        _show_interactive_graph()
    with tab3:
        _show_impact_analysis()


def _show_graph_analytics():
    analytics = api_get("/graph/analytics", timeout=10)
    stats     = api_get("/graph/statistics", timeout=10)

    if has_error(analytics) or analytics.get("total_nodes", 0) == 0:
        st.info("No graph data yet. Upload a circular first.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nodes",           analytics.get("total_nodes", 0))
    c2.metric("Edges",           analytics.get("total_edges", 0))
    c3.metric("Longest chain",   analytics.get("longest_dependency_chain", 0))
    c4.metric("Avg degree",      analytics.get("avg_degree", 0))

    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🎯 Most Critical Obligations")
        st.caption("Highest downstream impact (out-degree)")
        for item in analytics.get("most_downstream_impact", []):
            o = item["obligation"]
            deg = item["out_degree"]
            if deg == 0:
                continue
            st.markdown(f"""
<div class="obl-card">
  <div class="obl-title">{o['title']}</div>
  {sev_badge(o.get("severity","medium"))}
  <div class="obl-meta"><span>⬇ {deg} downstream obligations</span><span style="font-size:0.75rem;color:var(--muted)">{o['id']}</span></div>
</div>""", unsafe_allow_html=True)

    with col2:
        st.markdown("#### 🔗 Most Depended Upon")
        st.caption("Highest in-degree (other obligations depend on these)")
        for item in analytics.get("most_depended_upon", []):
            o = item["obligation"]
            deg = item["in_degree"]
            if deg == 0:
                continue
            st.markdown(f"""
<div class="obl-card">
  <div class="obl-title">{o['title']}</div>
  {sev_badge(o.get("severity","medium"))}
  <div class="obl-meta"><span>⬆ depended on by {deg} obligations</span></div>
</div>""", unsafe_allow_html=True)

    # Betweenness centrality
    top_bc = analytics.get("top_betweenness_centrality", [])
    if any(item["score"] > 0 for item in top_bc):
        st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
        st.markdown("#### 🕸 Betweenness Centrality — Most Connected Nodes")
        st.caption("Obligations that sit on the most dependency paths")
        bc_df = pd.DataFrame([
            {"Obligation": item["obligation"]["title"][:60],
             "Centrality Score": item["score"],
             "Severity": item["obligation"].get("severity","—")}
            for item in top_bc if item["score"] > 0
        ])
        if not bc_df.empty:
            st.dataframe(bc_df, use_container_width=True, hide_index=True)


def _show_interactive_graph():
    graph_data = api_get("/graph/export/json", timeout=15)
    if has_error(graph_data) or not graph_data.get("nodes"):
        st.info("No graph data yet.")
        return

    nodes = graph_data["nodes"]
    edges = graph_data["edges"]

    try:
        from pyvis.network import Network
        import tempfile, pathlib

        net = Network(height="520px", width="100%", directed=True,
                      bgcolor="#131826", font_color="#E2E8F0")
        net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=120)

        color_map = {
            "high":   {"background": "#EF4444", "border": "#B91C1C"},
            "medium": {"background": "#F59E0B", "border": "#D97706"},
            "low":    {"background": "#22C55E", "border": "#16A34A"},
        }
        ev_color_map = {"green": "#22C55E", "yellow": "#F59E0B", "red": "#EF4444"}

        for node in nodes:
            sev = node.get("severity", "medium")
            col = color_map.get(sev, color_map["medium"])
            ev_col = ev_color_map.get(node.get("evidence_status","red"), "#EF4444")
            label = node["label"][:40] + ("…" if len(node["label"]) > 40 else "")
            net.add_node(
                node["id"],
                label=label,
                title=f"<b>{node['label']}</b><br>Severity: {sev}<br>Evidence: {node.get('evidence_status','—')}",
                color={"background": col["background"], "border": ev_col,
                       "highlight": {"background": "#7C3AED", "border": "#A78BFA"}},
                size=16 + min(node.get("evidence_count", 0) * 2, 14),
                font={"color": "#E2E8F0", "size": 11},
            )

        edge_style = {"depends_on": "#64748B", "supersedes": "#A78BFA", "cross_reference": "#34D399", "related": "#475569"}
        for edge in edges:
            col = edge_style.get(edge.get("type", "related"), "#475569")
            dashes = edge.get("type") == "supersedes"
            net.add_edge(edge["source"], edge["target"], color=col,
                         dashes=dashes, arrows="to", width=1.5)

        net.set_options('{"interaction":{"hover":true,"navigationButtons":true},"physics":{"stabilization":{"iterations":150}}}')

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            net.save_graph(f.name)
            html_content = pathlib.Path(f.name).read_text(encoding="utf-8")

        # Legend
        st.markdown("""
<div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:12px;font-size:0.8rem">
  <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#EF4444;margin-right:5px"></span>High severity</span>
  <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#F59E0B;margin-right:5px"></span>Medium severity</span>
  <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#22C55E;margin-right:5px"></span>Low severity</span>
  <span style="color:var(--muted)">Border = evidence status &nbsp;|&nbsp; Size = evidence count &nbsp;|&nbsp; Dashed edge = supersedes</span>
</div>""", unsafe_allow_html=True)

        st.components.v1.html(html_content, height=530, scrolling=False)

    except ImportError:
        st.warning("pyvis not installed. Run: `pip install pyvis`")
        # Fallback: plotly scatter
        _plotly_graph_fallback(nodes, edges)


def _plotly_graph_fallback(nodes, edges):
    import networkx as nx
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["id"], **n)
    for e in edges:
        G.add_edge(e["source"], e["target"])

    pos = nx.spring_layout(G, seed=42)
    edge_x, edge_y = [], []
    for s, t in G.edges():
        if s in pos and t in pos:
            edge_x += [pos[s][0], pos[t][0], None]
            edge_y += [pos[s][1], pos[t][1], None]

    node_x = [pos[n][0] for n in G.nodes() if n in pos]
    node_y = [pos[n][1] for n in G.nodes() if n in pos]
    sev_colors = {"high": "#EF4444", "medium": "#F59E0B", "low": "#22C55E"}
    node_colors = [sev_colors.get(G.nodes[n].get("severity","medium"), "#F59E0B") for n in G.nodes() if n in pos]
    node_texts = [G.nodes[n].get("label", n)[:30] for n in G.nodes() if n in pos]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                             line=dict(color="#1E293B", width=1), hoverinfo="none"))
    fig.add_trace(go.Scatter(x=node_x, y=node_y, mode="markers+text",
                             marker=dict(size=12, color=node_colors),
                             text=node_texts, textposition="top center",
                             textfont=dict(color="#94A3B8", size=9)))
    fig.update_layout(paper_bgcolor="#0B0F19", plot_bgcolor="#0B0F19",
                      showlegend=False, height=480,
                      xaxis=dict(showgrid=False, zeroline=False, visible=False),
                      yaxis=dict(showgrid=False, zeroline=False, visible=False))
    st.plotly_chart(fig, use_container_width=True)


def _show_impact_analysis():
    stats = api_get("/graph/statistics", timeout=10)
    total = stats.get("total_obligations", 0) if not has_error(stats) else 0
    if total == 0:
        st.info("No obligations in graph yet.")
        return
    st.caption(f"{total} obligations in graph.")
    obl_id = st.text_input("Enter Obligation ID", placeholder="e.g. SEBI_CIRCULAR_obl_0")
    if not obl_id:
        return

    impact = api_get(f"/graph/impact/{obl_id}", timeout=10)
    if has_error(impact):
        st.error(f"Obligation not found: {obl_id}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Directly Affected",   len(impact.get("directly_affected", [])))
    c2.metric("Indirectly Affected", len(impact.get("indirectly_affected", [])))
    c3.metric("Total Affected",      impact.get("total_affected", 0))

    direct = impact.get("directly_affected", [])
    if direct:
        st.markdown("**Directly affected obligations:**")
        for d in direct[:10]:
            obl = api_get(f"/obligations/{d}", timeout=5)
            title = obl.get("title", d) if not has_error(obl) else d
            sev   = obl.get("severity", "medium") if not has_error(obl) else "medium"
            st.markdown(f'<div class="obl-card" style="padding:10px 16px"><span style="font-size:0.85rem;font-weight:600">{title}</span>&nbsp;{sev_badge(sev)}<br><span style="font-size:0.75rem;color:var(--muted)">{d}</span></div>', unsafe_allow_html=True)

    # Regulatory timeline
    tl = api_get(f"/obligations/{obl_id}/timeline", timeout=5)
    if not has_error(tl) and tl.get("version_timeline"):
        st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
        st.markdown("#### 📅 Regulatory Evolution Timeline")
        for entry in tl["version_timeline"]:
            changes = ", ".join(entry.get("changes", ["—"]))
            ts = str(entry.get("timestamp", ""))[:10]
            st.markdown(f"""
<div style="display:flex;gap:12px;margin-bottom:8px;align-items:flex-start">
  <div style="width:80px;font-size:0.75rem;color:var(--muted);padding-top:2px">{ts}</div>
  <div style="width:2px;background:var(--border);flex-shrink:0"></div>
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 14px;flex:1">
    <span style="font-size:0.78rem;color:var(--accent-lt)">v{entry.get("version","?")}</span>
    &nbsp;<span style="font-size:0.78rem;color:var(--muted)">{entry.get("circular_id","—")}</span>
    <br><span style="font-size:0.82rem">{changes}</span>
  </div>
</div>""", unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────────────
# PAGE: COMPLIANCE MAPPING
# ─────────────────────────────────────────────────────────────────────────────

def show_compliance_page(intermediary_type: str):
    st.markdown(f"## 📋 Compliance — {intermediary_type.replace('_',' ').title()}")

    mapping = api_get(f"/compliance/mapping/{intermediary_type}", timeout=15)
    scores  = api_get(f"/compliance/score/{intermediary_type}", timeout=10)

    if has_error(mapping):
        st.info("No compliance data yet. Upload a circular first.")
        return

    score_val = scores.get("compliance_score", 0.0) if not has_error(scores) else 0.0
    pct_color = "green" if score_val >= 75 else "yellow" if score_val >= 50 else "red"

    st.markdown(f"""
<div class="rg-card" style="display:flex;align-items:center;gap:32px;flex-wrap:wrap">
  <div>
    <div class="kpi-val" style="font-size:3rem;color:{'var(--low)' if score_val>=75 else 'var(--medium)' if score_val>=50 else 'var(--high)'}">{score_val:.0f}%</div>
    <div class="kpi-lbl">Compliance Score</div>
    {progress_bar(score_val, pct_color)}
  </div>
  <div style="display:flex;gap:24px;flex-wrap:wrap">
    <div><div class="kpi-val" style="font-size:1.6rem">{mapping.get("applicable_obligations_count",0)}</div><div class="kpi-lbl">Applicable</div></div>
    <div><div class="kpi-val high" style="font-size:1.6rem">{mapping.get("critical_gaps_count",0)}</div><div class="kpi-lbl">Critical Gaps</div></div>
    <div><div class="kpi-val" style="font-size:1.6rem;color:var(--muted)">{mapping.get("not_applicable_count",0)}</div><div class="kpi-lbl">Not Applicable</div></div>
  </div>
</div>""", unsafe_allow_html=True)

    # Action items table
    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    st.markdown("### 🎯 Priority Action Items")
    items = mapping.get("action_items", [])
    if items:
        for item in items[:15]:
            pb = priority_badge(item.get("priority","normal"))
            ev_needed = ", ".join(item.get("evidence_needed", [])[:3]) or "—"
            st.markdown(f"""
<div class="obl-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px">
    <div class="obl-title">{pb} {item.get("action","")[:100]}</div>
    <span style="font-size:0.78rem;color:var(--muted)">{item.get("deadline","TBD")}</span>
  </div>
  <div class="obl-meta">
    <span>🏢 {item.get("responsible_party","—")}</span>
    <span>📎 Evidence: {ev_needed}</span>
  </div>
</div>""", unsafe_allow_html=True)

    # Downloadable report button
    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    st.markdown("### 📄 Export Compliance Report")
    st.caption("Download a full HTML compliance report for this intermediary type.")
    report_url = f"http://localhost:8000/api/v1/compliance/report/{intermediary_type}"
    st.markdown(f'<a href="{report_url}" target="_blank"><button style="background:var(--accent);color:white;border:none;border-radius:8px;padding:10px 22px;font-size:0.9rem;font-weight:600;cursor:pointer">⬇ Download HTML Report</button></a>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: EVIDENCE GAPS
# ─────────────────────────────────────────────────────────────────────────────

def show_evidence_page(intermediary_type: str):
    st.markdown("## ⚠️ Evidence Gaps")

    data = api_get("/evidence/gaps", timeout=15)
    if has_error(data) or not data.get("gaps"):
        st.markdown('<div class="empty-state anim-fade-in"><div class="empty-icon">✅</div><div class="empty-text">No evidence gaps — all obligations have complete evidence!</div></div>', unsafe_allow_html=True)
        return

    gaps = data.get("gaps", [])
    missing = [g for g in gaps if g.get("evidence_status") == "red"]
    partial = [g for g in gaps if g.get("evidence_status") == "yellow"]

    st.markdown(f"""
<div class="kpi-row anim-slide-up">
  <div class="kpi-card"><div class="kpi-val">{data.get("total_gaps",0)}</div><div class="kpi-lbl">Total Gaps</div></div>
  <div class="kpi-card"><div class="kpi-val high">{len(missing)}</div><div class="kpi-lbl">🔴 Missing</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--medium)">{len(partial)}</div><div class="kpi-lbl">🟡 Partial</div></div>
</div>""", unsafe_allow_html=True)

    # ── Evidence upload panel ─────────────────────────────────────────────
    with st.expander("📤 Upload Evidence Document", expanded=False):
        st.caption("Upload a PDF or TXT document and match it semantically against an obligation.")
        all_ids = [g["obligation_id"] for g in gaps]
        selected_obl = st.selectbox("Select obligation", all_ids,
                                    format_func=lambda x: next((g["title"] for g in gaps if g["obligation_id"]==x), x))
        ev_file = st.file_uploader("Evidence document (PDF/TXT)", type=["pdf", "txt", "docx"],
                                   key="evidence_upload")
        uploader = st.text_input("Uploaded by", value="compliance_officer")

        if st.button("🔍 Analyse & Match", type="primary", disabled=not ev_file):
            with st.spinner("🤖 Running semantic evidence analysis…"):
                import httpx as _httpx
                try:
                    ev_bytes = ev_file.read()
                    resp = _httpx.post(
                        f"{API_BASE_URL}/evidence/upload",
                        data={"obligation_id": selected_obl, "uploaded_by": uploader},
                        files={"file": (ev_file.name, ev_bytes, "application/octet-stream")},
                        timeout=120.0,
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        score_pct = int(result.get("match_score", 0) * 100)
                        ev_st = result.get("evidence_status", "red")
                        color = {"green": "var(--ev-green)", "yellow": "var(--ev-yellow)", "red": "var(--ev-red)"}.get(ev_st, "var(--ev-red)")
                        pulse_class = "anim-success" if ev_st == "green" else ""
                        st.markdown(f"""
<div class="rg-card {pulse_class}" style="border-color:{color}">
  <div style="font-size:1.5rem;font-weight:700;color:{color}">{score_pct}% Match</div>
  <div style="font-size:0.82rem;color:var(--muted);margin:4px 0">{ev_badge(ev_st)} via {result.get("method","—")}</div>
  {render_evidence_reasoning(result.get("per_requirement",[]), result.get("overall_reasoning",""), result.get("method","keyword_fallback"))}
</div>""", unsafe_allow_html=True)
                        st.toast(f"Evidence matched: {score_pct}% — {ev_st.upper()}", icon="🔍")
                        st.rerun()
                    else:
                        st.error(f"Upload failed: {resp.text[:200]}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)

    # ── Gap list ──────────────────────────────────────────────────────────
    for g in gaps[:20]:
        ev  = g.get("evidence_status", "red")
        sev = g.get("severity", "medium")
        pulse = ' anim-alert' if ev == 'red' and sev == 'high' else ''

        with st.expander(f"{'🔴' if ev=='red' else '🟡'} {g['title']} — {sev.upper()}"):
            reqs = g.get("evidence_requirements") or []

            # Fetch latest evidence entry for this obligation (shows LLM reasoning)
            ev_index = api_get(f"/evidence/list/{g['obligation_id']}", timeout=5)
            latest_ev = None
            if not has_error(ev_index) and ev_index.get("evidence"):
                latest_ev = ev_index["evidence"][-1]  # most recent upload

            if latest_ev and latest_ev.get("per_requirement"):
                # Show LLM reasoning from the last upload
                score_pct = int(latest_ev.get("match_score", 0) * 100)
                ev_color = {"green": "var(--ev-green)", "yellow": "var(--ev-yellow)", "red": "var(--ev-red)"}.get(ev, "var(--ev-red)")
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
  <span style="font-size:1.1rem;font-weight:700;color:{ev_color}">{score_pct}%</span>
  {ev_badge(ev)}
  <span style="font-size:0.78rem;color:var(--muted)">Last upload: {latest_ev.get("filename","—")} · {str(latest_ev.get("uploaded_at",""))[:10]}</span>
</div>""", unsafe_allow_html=True)
                st.markdown(
                    render_evidence_reasoning(
                        latest_ev["per_requirement"],
                        latest_ev.get("overall_reasoning", ""),
                        latest_ev.get("method", "keyword_fallback"),
                    ),
                    unsafe_allow_html=True,
                )
            else:
                # No evidence uploaded yet — show checklist
                chk = api_get(f"/evidence/checklist/{g['obligation_id']}", timeout=5)
                if not has_error(chk) and chk.get("checklist"):
                    pct  = chk.get("completion_pct", 0)
                    prog = chk.get("progress", "0/0")
                    st.markdown(f"**Evidence checklist** ({prog} — {pct:.0f}% complete)")
                    st.markdown(progress_bar(pct), unsafe_allow_html=True)
                    for ci in chk["checklist"]:
                        icon = "✅" if ci["completed"] else "☐"
                        st.markdown(f"{icon} {ci['label']}")
                else:
                    for req in reqs:
                        st.markdown(f"☐ {req}")
                st.caption("Upload evidence above to run semantic analysis.")

            st.markdown(f"""
<div class="obl-meta" style="margin-top:8px">
  <span>ID: <code style="font-size:0.75rem">{g['obligation_id']}</code></span>
  <span>Circular: {g.get('circular_id','—')}</span>
</div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: COMPLIANCE ACTIONS (Tier 1A)
# ─────────────────────────────────────────────────────────────────────────────

def show_actions_page(intermediary_type: str):
    st.markdown("## 🎯 Compliance Actions")
    st.markdown('<p class="muted">Structured, assignable work items generated from obligations. Sorted by priority + urgency.</p>', unsafe_allow_html=True)

    # ── Notification panel ────────────────────────────────────────────────
    notif_cfg = api_get("/notifications/config", timeout=5)
    email_ok   = notif_cfg.get("email_configured", False) if not has_error(notif_cfg) else False
    webhook_ok = notif_cfg.get("webhook_configured", False) if not has_error(notif_cfg) else False
    channels_txt = " + ".join(filter(None, [
        ("📧 Email" if email_ok else ""),
        ("💬 Slack" if webhook_ok else ""),
    ])) or "⚠ No channels configured"

    with st.expander(f"🔔 Send Compliance Alert Digest  —  {channels_txt}", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            due_soon = st.number_input("Alert if due within (days)", min_value=1, max_value=90, value=7)
        with c2:
            min_sev = st.selectbox("Min severity", ["low", "medium", "high"], index=1)
        with c3:
            dry_run = st.checkbox("Dry run (preview only)", value=True)

        col_prev, col_send = st.columns([1, 1])

        with col_prev:
            if st.button("👁 Preview alerts", use_container_width=True):
                with st.spinner("Scanning obligations…"):
                    preview = api_get(
                        f"/notifications/preview?intermediary_type={intermediary_type}"
                        f"&due_soon_days={due_soon}&min_severity={min_sev}",
                        timeout=15,
                    )
                if has_error(preview):
                    st.error(f"Preview failed: {preview.get('_error')}")
                else:
                    total = preview.get("total_alerts", 0)
                    has_crit = preview.get("has_critical", False)
                    crit_html = '<span style="color:var(--high);font-weight:700">⚠ CRITICAL</span> — ' if has_crit else ""
                    st.markdown(f"""
<div class="rg-card anim-fade-in" style="{'border-color:var(--high)' if has_crit else ''}">
  <div style="font-size:1rem;font-weight:600;margin-bottom:8px">{crit_html}{total} alert(s) found</div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:0.85rem">
    <span>⚠ Overdue: <b style="color:var(--high)">{len(preview.get('overdue',[]))}</b></span>
    <span>🔔 Due soon: <b style="color:var(--medium)">{len(preview.get('due_soon',[]))}</b></span>
    <span>🆕 New HIGH: <b style="color:var(--accent-lt)">{len(preview.get('new_high',[]))}</b></span>
  </div>
</div>""", unsafe_allow_html=True)

        with col_send:
            btn_label = "📤 Send Now" if not dry_run else "📋 Test (no send)"
            if st.button(btn_label, type="primary", use_container_width=True):
                with st.spinner("Sending notifications…" if not dry_run else "Running test…"):
                    result = api_post("/notifications/send", {
                        "intermediary_type": intermediary_type,
                        "due_soon_days": due_soon,
                        "min_severity": min_sev,
                        "dry_run": dry_run,
                    })
                if has_error(result):
                    st.error(f"Failed: {result.get('_error')}")
                else:
                    total = result.get("total_alerts", 0)
                    email_sent   = result.get("email",   {}).get("sent", False)
                    webhook_sent = result.get("webhook", {}).get("sent", False)
                    email_err    = result.get("email",   {}).get("error", "")
                    webhook_err  = result.get("webhook", {}).get("error", "")

                    status_color = "var(--low)" if (email_sent or webhook_sent) else "var(--medium)"
                    st.markdown(f"""
<div class="rg-card anim-success" style="border-color:{status_color}">
  <div style="font-size:0.95rem;font-weight:600;margin-bottom:8px">
    {'✅ Sent' if not dry_run else '✅ Test complete'} — {total} alert(s)
  </div>
  <div style="font-size:0.82rem;display:flex;flex-direction:column;gap:4px">
    <span>📧 Email: {'<b style="color:var(--low)">Sent ✓</b>' if email_sent else f'<span style="color:var(--muted)">{"Not configured" if not email_ok else email_err or "Not sent"}</span>'}</span>
    <span>💬 Slack: {'<b style="color:var(--low)">Sent ✓</b>' if webhook_sent else f'<span style="color:var(--muted)">{"Not configured" if not webhook_ok else webhook_err or "Not sent"}</span>'}</span>
  </div>
  <div style="font-size:0.78rem;color:var(--muted);margin-top:6px">{result.get("summary","")}</div>
</div>""", unsafe_allow_html=True)
                    st.toast("Notifications sent!" if (email_sent or webhook_sent) else "Test complete", icon="🔔")

        if not (email_ok or webhook_ok):
            st.info("Configure `NOTIFY_EMAIL_TO`/`SMTP_USER` or `NOTIFY_WEBHOOK_URL` in your `.env` to enable sending.")

    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)

    data = api_get(f"/actions?limit=100", timeout=10)
    if has_error(data) or not data.get("actions"):
        st.info("No action tasks yet. Upload a circular to generate them.")
        return

    actions = data["actions"]
    critical = [a for a in actions if a.get("priority") == "critical"]
    high     = [a for a in actions if a.get("priority") == "high"]
    overdue  = [a for a in actions if a.get("overdue")]

    st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card"><div class="kpi-val">{len(actions)}</div><div class="kpi-lbl">Total Tasks</div></div>
  <div class="kpi-card"><div class="kpi-val high">{len(critical)}</div><div class="kpi-lbl">Critical</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--medium)">{len(high)}</div><div class="kpi-lbl">High</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--high)">{len(overdue)}</div><div class="kpi-lbl">Overdue</div></div>
</div>""", unsafe_allow_html=True)

    filter_p = st.selectbox("Filter by priority", ["All", "critical", "high", "medium", "low"])
    if filter_p != "All":
        actions = [a for a in actions if a.get("priority") == filter_p]

    for action in actions[:25]:
        pb   = priority_badge(action.get("priority","medium"))
        days = action.get("days_remaining")
        if days is not None and days < 0:
            days_str = f'<span style="color:var(--high);font-weight:600">⚠ {abs(days)}d overdue</span>'
        elif days is not None:
            days_str = f'{days}d remaining'
        else:
            days_str = action.get("due_date") or "No deadline"

        ev_needed = ", ".join(action.get("evidence_required", [])[:3]) or "—"

        with st.expander(f"{pb.replace('<','<').replace('>','>')} {action.get('title','')[:90]}", expanded=False):
            st.markdown(f"""
<div class="rg-card" style="margin:0">
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px">
    <div><span style="font-size:0.75rem;color:var(--muted)">ACTION ID</span><br><code style="font-size:0.82rem;color:var(--accent-lt)">{action.get("action_id","—")}</code></div>
    <div><span style="font-size:0.75rem;color:var(--muted)">DEPARTMENT</span><br><b>{action.get("department","—")}</b></div>
    <div><span style="font-size:0.75rem;color:var(--muted)">OWNER</span><br>{action.get("owner","—")}</div>
    <div><span style="font-size:0.75rem;color:var(--muted)">DUE</span><br>{days_str}</div>
  </div>
  <div style="font-size:0.85rem;color:var(--text);margin-bottom:10px">{action.get("description","")[:300]}</div>
  <div style="font-size:0.78rem;color:var(--muted)">📎 Evidence required: {ev_needed}</div>
</div>""", unsafe_allow_html=True)

            if action.get("steps"):
                st.markdown(
                    render_sop_steps(action["steps"], "llm"),
                    unsafe_allow_html=True,
                )


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: AUDIT TRAIL
# ─────────────────────────────────────────────────────────────────────────────

def show_audit_page():
    st.markdown("## 🔒 Audit Trail")

    summary = api_get("/audit/summary", timeout=10)
    if not has_error(summary):
        st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card"><div class="kpi-val">{summary.get("total_events",0)}</div><div class="kpi-lbl">Total Events</div></div>
  <div class="kpi-card"><div class="kpi-val green">{summary.get("circulars_processed",0)}</div><div class="kpi-lbl">Circulars Processed</div></div>
  <div class="kpi-card"><div class="kpi-val high">{summary.get("failures",0)}</div><div class="kpi-lbl">Failures</div></div>
</div>""", unsafe_allow_html=True)

    data = api_get("/audit/trail", timeout=15)
    entries = data.get("entries", [])[:50]
    if not entries:
        st.info("No audit events yet.")
        return

    for e in reversed(entries):
        ts  = e.get("timestamp","")[:19]
        evt = e.get("event_type","")
        ok  = "✅" if e.get("status") == "success" else "❌"
        det = e.get("details",{})
        det_str = "  ".join(f"{k}: {v}" for k, v in det.items() if not isinstance(v, dict))[:120]
        st.markdown(
            f'<div style="font-size:0.82rem;padding:6px 0;border-bottom:1px solid var(--border)">'
            f'<code style="color:var(--muted);font-size:0.75rem">{ts}</code> {ok} '
            f'<b style="color:var(--accent-lt)">{evt}</b>'
            f'<span style="color:var(--muted);margin-left:10px">{det_str}</span></div>',
            unsafe_allow_html=True
        )



# ─────────────────────────────────────────────────────────────────────────────
# MAIN — nav + routing
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # Inject design system CSS
    st.markdown(DESIGN_CSS, unsafe_allow_html=True)

    # ── Sidebar brand header ────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
<div class="sidebar-brand">
  <div class="sidebar-logo">🏛 RegGraph</div>
  <div class="sidebar-tag">Agentic Compliance System</div>
  <div style="font-size:0.7rem;color:#334155;margin-top:2px">SEBI · Multi-Agent Pipeline</div>
</div>""", unsafe_allow_html=True)
        st.markdown('<hr class="rg-divider" style="margin:8px 0 12px 0">', unsafe_allow_html=True)

        # Intermediary selector
        intermediary_type = st.selectbox(
            "Intermediary",
            ["stockbroker", "depository", "listed_company", "investment_adviser", "fiduciary", "rta"],
            key="intermediary_selector",
        )

        st.markdown('<hr class="rg-divider" style="margin:10px 0">', unsafe_allow_html=True)

        # Navigation — streamlit-option-menu if available, else radio
        try:
            from streamlit_option_menu import option_menu
            page = option_menu(
                menu_title=None,
                options=[
                    "Upload Circular",
                    "Document Intelligence",
                    "Ask the Circular",
                    "Dashboard",
                    "Obligations",
                    "Graph",
                    "Compliance",
                    "Evidence Gaps",
                    "Actions",
                    "Audit Trail",
                ],
                icons=[
                    "upload",
                    "cpu",
                    "chat-dots",
                    "speedometer2",
                    "list-check",
                    "diagram-3",
                    "shield-check",
                    "exclamation-triangle",
                    "lightning-charge",
                    "journal-text",
                ],
                default_index=0,
                styles={
                    "container": {
                        "padding": "0",
                        "background-color": "#131826",
                    },
                    "icon": {"color": "#64748B", "font-size": "14px"},
                    "nav-link": {
                        "font-size": "0.88rem",
                        "color": "#94A3B8",
                        "padding": "10px 14px",
                        "border-radius": "8px",
                        "margin": "2px 0",
                    },
                    "nav-link-selected": {
                        "background-color": "rgba(124,58,237,0.20)",
                        "color": "#A78BFA",
                        "font-weight": "600",
                    },
                },
            )
        except ImportError:
            page = st.radio(
                "Navigation",
                ["Upload Circular", "Document Intelligence", "Ask the Circular",
                 "Dashboard", "Obligations", "Graph",
                 "Compliance", "Evidence Gaps", "Actions", "Audit Trail"],
                label_visibility="collapsed",
            )

        # Sidebar stats footer
        st.markdown('<hr class="rg-divider" style="margin:12px 0 8px 0">', unsafe_allow_html=True)
        stats = api_get("/graph/statistics", timeout=5)
        if not has_error(stats) and stats.get("total_obligations", 0) > 0:
            st.markdown(f"""
<div style="font-size:0.75rem;color:var(--muted);line-height:1.8">
  📊 <b style="color:var(--text)">{stats.get("total_obligations",0)}</b> obligations<br>
  🌐 <b style="color:var(--text)">{stats.get("total_edges",0)}</b> graph edges<br>
  📁 <b style="color:var(--text)">{stats.get("circulars_ingested",0)}</b> circulars ingested<br>
  🔴 <b style="color:var(--high)">{stats.get("high_severity_count",0)}</b> high severity
</div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.75rem;color:var(--muted)">No data yet</div>', unsafe_allow_html=True)

    # ── Page routing ────────────────────────────────────────────────────────
    if page == "Upload Circular":
        show_upload_page()
    elif page == "Document Intelligence":
        intel_views.render_intelligence_page(intermediary_type)
    elif page == "Ask the Circular":
        intel_views.render_chat_page()
    elif page == "Dashboard":
        show_overview_page(intermediary_type)
    elif page == "Obligations":
        show_obligations_page(intermediary_type)
    elif page == "Graph":
        show_graph_page()
    elif page == "Compliance":
        show_compliance_page(intermediary_type)
    elif page == "Evidence Gaps":
        show_evidence_page(intermediary_type)
    elif page == "Actions":
        show_actions_page(intermediary_type)
    elif page == "Audit Trail":
        show_audit_page()


if __name__ == "__main__":
    main()
