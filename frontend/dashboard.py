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

st.set_page_config(
    page_title="RegGraph — Agentic Compliance",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = "http://localhost:8000/api/v1"

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
    for line in lines[:25]:
        if line.lower().startswith("sub:"):
            title = line[4:].strip()
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

    uploaded_file = st.file_uploader("Drop circular PDF here", type=["pdf", "txt"])

    doc_text = ""; file_bytes = b""; filename = ""; auto_id = ""; auto_title = ""

    if uploaded_file:
        file_bytes = uploaded_file.read()
        filename   = uploaded_file.name or ""
        with st.spinner("Reading file…"):
            if filename.lower().endswith(".pdf"):
                doc_text = _extract_pdf_text(file_bytes)
            else:
                try:
                    doc_text = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    doc_text = file_bytes.decode("latin-1")
        auto_id, auto_title = _parse_metadata(doc_text)
        st.success(f"✅ Read **{len(doc_text):,} characters** from `{filename}`")
    else:
        doc_text = st.text_area("Or paste circular text", height=120,
                                placeholder="Paste full circular text here…")
        if doc_text.strip():
            auto_id, auto_title = _parse_metadata(doc_text)

    col1, col2 = st.columns(2)
    with col1:
        circular_id = st.text_input("Circular ID", value=auto_id)
    with col2:
        circular_title = st.text_input("Title", value=auto_title)

    intermediary_types = st.multiselect(
        "Intermediary types",
        ["stockbroker", "depository", "listed_company", "investment_adviser", "fiduciary", "rta"],
        default=["stockbroker", "depository", "listed_company"],
    )

    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    can_run = bool(doc_text.strip()) and bool(circular_id.strip())
    if st.button("🚀 Run Agent Pipeline", type="primary", disabled=not can_run, use_container_width=True):
        _run_pipeline(circular_id, circular_title, doc_text, file_bytes, filename, intermediary_types)


def _run_pipeline(circular_id, circular_title, doc_text, file_bytes, filename, intermediary_types):
    stat_slot  = st.empty()
    step_slot  = st.empty()

    step_results = [""] * len(PIPELINE_STEPS)

    def render(done: int, error: str = ""):
        step_slot.markdown(
            f'<div class="rg-card">{_render_stepper(done, step_results, error)}</div>',
            unsafe_allow_html=True
        )

    # Live stat row above stepper
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
                timeout=600.0,
            )
        else:
            render(1); step_results[0] = "Text chunked into sections"
            resp = httpx.post(
                f"{API_BASE_URL}/circulars/upload",
                json={"circular_id": circular_id, "title": circular_title,
                      "document_text": doc_text, "intermediary_types": intermediary_types},
                timeout=600.0,
            )

        if resp.status_code != 200:
            render(0, error=resp.text[:300])
            return

        result = resp.json()
        n_extracted = result.get("extracted_obligations_count", 0)
        n_new       = result.get("new_obligations_count", 0)
        n_mod       = result.get("modified_obligations_count", 0)
        n_sup       = result.get("superseded_obligations_count", 0)
        risk_level  = result.get("risk_level", "medium")

        step_results[1] = f"{n_extracted} obligations extracted"
        step_results[2] = f"NEW={n_new}  MODIFIED={n_mod}  SUPERSEDED={n_sup}"
        step_results[3] = "Impact propagation complete"
        step_results[4] = f"Action tasks generated for {', '.join(intermediary_types)}"
        step_results[5] = "Graph saved · audit logged · metrics recorded"
        render(6)

        # Update stat row
        stat_slot.markdown(
            f'<div class="kpi-row">'
            f'<div class="kpi-card accent"><div class="kpi-val">{n_extracted}</div><div class="kpi-lbl">Extracted</div></div>'
            f'<div class="kpi-card"><div class="kpi-val" style="color:var(--accent-lt)">{n_new}</div><div class="kpi-lbl">NEW</div></div>'
            f'<div class="kpi-card"><div class="kpi-val" style="color:var(--medium)">{n_mod}</div><div class="kpi-lbl">MODIFIED</div></div>'
            f'<div class="kpi-card"><div class="kpi-val" style="color:var(--muted)">{n_sup}</div><div class="kpi-lbl">SUPERSEDED</div></div>'
            f'</div>', unsafe_allow_html=True
        )

        st.toast(f"✅ Pipeline complete — {n_extracted} obligations, {n_new} new, {n_mod} modified", icon="🏛")

        # ── Compliance Copilot / Impact Simulator card ────────────────────
        st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
        st.markdown("### 🤖 Compliance Copilot Summary")

        copilot = api_get("/copilot/summary", timeout=10)
        if not has_error(copilot) and copilot.get("summary"):
            s = copilot["summary"]
            affected = ", ".join(copilot.get("affected_intermediaries", []))
            depts    = ", ".join(copilot.get("departments_impacted", []))
            effort   = copilot.get("effort_estimate", {})
            est_days = effort.get("estimated_implementation_days", "—")

            top3 = copilot.get("top_3_immediate_actions", [])
            actions_html = ""
            for a in top3:
                pb = priority_badge(a.get("priority", "medium"))
                days_txt = f"due in {a['days_remaining']}d" if a.get("days_remaining") is not None else a.get("due_date") or "—"
                actions_html += f'<li style="margin:4px 0;">{pb} <b>{a["title"]}</b> — <span style="color:var(--muted)">{a["department"]} · {days_txt}</span></li>'

            st.markdown(f"""
<div class="copilot-card">
  <div class="copilot-title">📋 What changed? What to do next?</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div>
      <p style="color:var(--muted);font-size:0.78rem;margin-bottom:4px">AFFECTED INTERMEDIARIES</p>
      <p>{affected or '—'}</p>
      <p style="color:var(--muted);font-size:0.78rem;margin-bottom:4px;margin-top:12px">DEPARTMENTS IMPACTED</p>
      <p>{depts or '—'}</p>
    </div>
    <div>
      <p style="color:var(--muted);font-size:0.78rem;margin-bottom:4px">TASKS CREATED</p>
      <p style="font-size:1.4rem;font-weight:700;color:var(--accent-lt)">{s.get("total_tasks_created","—")}</p>
      <p style="color:var(--muted);font-size:0.78rem;margin-bottom:4px;margin-top:8px">EST. IMPLEMENTATION</p>
      <p style="font-size:1.1rem;font-weight:600">{est_days} days <span style="font-size:0.75rem;color:var(--muted)">(estimate)</span></p>
    </div>
  </div>
  <p style="color:var(--muted);font-size:0.78rem;margin:12px 0 4px">TOP 3 IMMEDIATE ACTIONS</p>
  <ul style="padding-left:16px;margin:0">{actions_html}</ul>
</div>""", unsafe_allow_html=True)
        else:
            risk_icon = "🔴" if risk_level == "high" else "🟡" if risk_level == "medium" else "🟢"
            st.info(f"{risk_icon} Risk level: **{risk_level.upper()}** · {n_extracted} obligations processed")

        # audit expander
        with st.expander("🔒 Audit trail for this run"):
            ar = api_get(f"/audit/trail?circular_id={circular_id}", timeout=10)
            for e in ar.get("entries", []):
                ts  = e.get("timestamp","")[:19]
                evt = e.get("event_type","")
                ok  = "✅" if e.get("status") == "success" else "❌"
                st.markdown(f'`{ts}` {ok} **{evt}**')

    except Exception as exc:
        render(0, error=str(exc))



# ─────────────────────────────────────────────────────────────────────────────
# PAGE: DASHBOARD OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

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

            # SOP
            sop = api_get(f"/obligations/{item['obligation_id']}/sop", timeout=5)
            if not has_error(sop) and sop.get("sop_steps"):
                st.markdown("**Standard Operating Procedure:**")
                for step in sop["sop_steps"]:
                    st.markdown(f"- {step}")

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
        st.markdown('<div class="empty-state"><div class="empty-icon">✅</div><div class="empty-text">No evidence gaps — all obligations have complete evidence!</div></div>', unsafe_allow_html=True)
        return

    gaps = [g for g in data.get("gaps", []) if intermediary_type in g.get("obligation_id", "") or True]
    missing = [g for g in gaps if g.get("evidence_status") == "red"]
    partial = [g for g in gaps if g.get("evidence_status") == "yellow"]

    st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card"><div class="kpi-val">{data.get("total_gaps",0)}</div><div class="kpi-lbl">Total Gaps</div></div>
  <div class="kpi-card"><div class="kpi-val high">{len(missing)}</div><div class="kpi-lbl">🔴 Missing</div></div>
  <div class="kpi-card"><div class="kpi-val" style="color:var(--medium)">{len(partial)}</div><div class="kpi-lbl">🟡 Partial</div></div>
</div>""", unsafe_allow_html=True)

    for g in gaps[:20]:
        ev  = g.get("evidence_status", "red")
        sev = g.get("severity", "medium")
        with st.expander(f"{'🔴' if ev=='red' else '🟡'} {g['title']} — {sev.upper()}"):
            reqs = g.get("evidence_requirements") or []
            # Fetch checklist for this obligation
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

            st.markdown(f"""
<div class="obl-meta" style="margin-top:8px">
  <span>ID: <code style="font-size:0.75rem">{g['obligation_id']}</code></span>
  <span>Circular: {g['circular_id']}</span>
</div>""", unsafe_allow_html=True)
            st.caption("Upload evidence via POST /api/v1/evidence/upload")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: COMPLIANCE ACTIONS (Tier 1A)
# ─────────────────────────────────────────────────────────────────────────────

def show_actions_page(intermediary_type: str):
    st.markdown("## 🎯 Compliance Actions")
    st.markdown('<p class="muted">Structured, assignable work items generated from obligations. Sorted by priority + urgency.</p>', unsafe_allow_html=True)

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
                st.markdown("**SOP Steps:**")
                for step in action["steps"]:
                    st.markdown(f"- {step}")


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
                ["Upload Circular", "Dashboard", "Obligations", "Graph",
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
