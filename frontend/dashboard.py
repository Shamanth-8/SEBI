"""
Streamlit dashboard for RegGraph - Interactive obligation graph visualization.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import httpx
import json
import re
import io
from typing import Dict, List

st.set_page_config(
    page_title="RegGraph - Regulatory Obligation Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_BASE_URL = "http://localhost:8000/api/v1"

if 'current_intermediary' not in st.session_state:
    st.session_state.current_intermediary = 'stockbroker'


def get_api_data(endpoint: str) -> Dict:
    try:
        response = httpx.get(f"{API_BASE_URL}{endpoint}", timeout=30.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API error: {str(e)}")
        return {}


def main():
    st.title("📊 RegGraph — SEBI Regulatory Compliance")
    st.caption("Agentic pipeline: circular PDF → obligations → impact analysis → compliance action items")

    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Select View",
        [
            "📤 Upload Circular",
            "📈 Dashboard Overview",
            "🔍 Search Obligations",
            "📋 Compliance Mapping",
            "🌐 Graph Analysis",
            "⚠️ Evidence Gaps",
            "🔗 Impact Analysis",
        ]
    )

    st.sidebar.markdown("---")
    intermediary_type = st.sidebar.selectbox(
        "Intermediary Type",
        ["stockbroker", "depository", "listed_company", "investment_adviser", "fiduciary", "rta"],
        key="intermediary_selector"
    )
    st.session_state.current_intermediary = intermediary_type

    if page == "📤 Upload Circular":
        show_upload_circular()
    elif page == "📈 Dashboard Overview":
        show_dashboard_overview(intermediary_type)
    elif page == "🔍 Search Obligations":
        show_search_obligations()
    elif page == "📋 Compliance Mapping":
        show_compliance_mapping(intermediary_type)
    elif page == "🌐 Graph Analysis":
        show_graph_analysis()
    elif page == "⚠️ Evidence Gaps":
        show_evidence_gaps(intermediary_type)
    elif page == "🔗 Impact Analysis":
        show_impact_analysis()


# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD PAGE
# ─────────────────────────────────────────────────────────────────────────────

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
    """Auto-detect circular ID and title from text."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Reference number — e.g. HO/43/15/12(3)2025-ISD-POD2/I/11734/2026
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

    # Title — "Sub:" line or second non-empty line
    title = ""
    for line in lines[:25]:
        if line.lower().startswith("sub:"):
            title = line[4:].strip()
            break
    if not title and len(lines) > 1:
        title = lines[1]

    return circular_id, title


def show_upload_circular():
    st.header("📤 Upload Regulatory Circular")

    st.info(
        "**How it works:** Drop your PDF → the system reads the Circular ID and Title "
        "automatically → click **Run Agent Pipeline** → done."
    )

    # ── file upload ──────────────────────────────────────────────────────────
    uploaded_file = st.file_uploader(
        "📎 Drop circular PDF here",
        type=["pdf", "txt"],
    )

    doc_text   = ""
    file_bytes = b""
    filename   = ""
    auto_id    = ""
    auto_title = ""

    if uploaded_file:
        file_bytes = uploaded_file.read()
        filename   = uploaded_file.name or ""

        with st.spinner("Reading file..."):
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
        doc_text = st.text_area(
            "Or paste circular text directly",
            height=150,
            placeholder="Paste the full text of the circular here..."
        )
        if doc_text.strip():
            auto_id, auto_title = _parse_metadata(doc_text)

    # ── editable fields (pre-filled) ─────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        circular_id = st.text_input("Circular ID", value=auto_id,
                                    help="Auto-detected from PDF. Edit if needed.")
    with col2:
        circular_title = st.text_input("Title", value=auto_title,
                                       help="Auto-detected from PDF. Edit if needed.")

    intermediary_types = st.multiselect(
        "Intermediary types",
        ["stockbroker", "depository", "listed_company", "investment_adviser", "fiduciary", "rta"],
        default=["stockbroker", "depository", "listed_company"],
        help="Leave as default if unsure — applies to all common SEBI intermediaries"
    )

    st.markdown("---")

    can_run = bool(doc_text.strip()) and bool(circular_id.strip())
    if st.button("🚀 Run Agent Pipeline", type="primary", disabled=not can_run):
        _run_pipeline(circular_id, circular_title, doc_text,
                      file_bytes, filename, intermediary_types)


def _run_pipeline(circular_id, circular_title, doc_text,
                  file_bytes, filename, intermediary_types):
    """Execute pipeline with live step display."""

    steps = [
        ("📄", "Extracting & chunking circular text"),
        ("🤖", "Extraction Agent — LLM reads each chunk, finds obligations"),
        ("🔍", "Diff Agent — classifies NEW / MODIFIED / SUPERSEDED"),
        ("🌐", "Impact Engine — BFS graph traversal for dependencies"),
        ("📋", "Mapping Agent — action items per intermediary type"),
        ("🔒", "Saving graph · updating audit log · recording metrics"),
    ]

    box = st.empty()

    def render(done: int, error: str = ""):
        lines = []
        for i, (icon, desc) in enumerate(steps):
            if i < done:
                lines.append(f"✅ &nbsp;{icon} **Step {i+1}** — {desc}")
            elif i == done and not error:
                lines.append(f"⏳ &nbsp;{icon} **Step {i+1}** — {desc} …")
            else:
                lines.append(f"⬜ &nbsp;Step {i+1} — {desc}")
        if error:
            lines.append(f"\n❌ **Error:** `{error}`")
        box.markdown("\n\n".join(lines))

    render(0)

    try:
        # use multipart for PDFs (backend does pdfplumber), JSON for text
        if file_bytes and filename.lower().endswith(".pdf"):
            render(1)
            resp = httpx.post(
                f"{API_BASE_URL}/circulars/upload-file",
                data={
                    "circular_id":      circular_id,
                    "title":            circular_title,
                    "intermediary_types": ",".join(intermediary_types),
                },
                files={"file": (filename, file_bytes, "application/pdf")},
                timeout=600.0,
            )
        else:
            render(1)
            resp = httpx.post(
                f"{API_BASE_URL}/circulars/upload",
                json={
                    "circular_id":      circular_id,
                    "title":            circular_title,
                    "document_text":    doc_text,
                    "intermediary_types": intermediary_types,
                },
                timeout=600.0,
            )

        if resp.status_code != 200:
            render(0, error=resp.text[:300])
            st.error(f"Pipeline error: {resp.text[:300]}")
            return

        render(6)
        result = resp.json()

        # ── results ───────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("📊 Pipeline Results")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Obligations Extracted", result.get("extracted_obligations_count", 0))
        c2.metric("🆕 NEW",                result.get("new_obligations_count", 0))
        c3.metric("✏️ MODIFIED",           result.get("modified_obligations_count", 0))
        c4.metric("🗑️ SUPERSEDED",         result.get("superseded_obligations_count", 0))

        c1, c2 = st.columns(2)
        c1.metric("Impact Score", f"{result.get('impact_score', 0):.2f}")
        risk  = result.get("risk_level", "medium")
        emoji = "🔴" if risk == "high" else "🟡" if risk == "medium" else "🟢"
        c2.markdown(f"**Risk Level:** {emoji} **{risk.upper()}**")

        st.success("✅ Done! Use the sidebar to explore **Dashboard Overview**, **Evidence Gaps**, or **Search Obligations**.")

        with st.expander("🔒 Audit Trail for this run"):
            ar = httpx.get(f"{API_BASE_URL}/audit/trail?circular_id={circular_id}", timeout=10)
            if ar.status_code == 200:
                for e in ar.json().get("entries", []):
                    ts  = e.get("timestamp", "")[:19]
                    evt = e.get("event_type", "")
                    det = json.dumps(e.get("details", {}), default=str)
                    ok  = "✅" if e.get("status") == "success" else "❌"
                    st.markdown(f"`{ts}` {ok} **{evt}**  \n`{det}`")

    except Exception as exc:
        render(0, error=str(exc))
        st.error(f"Error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# OTHER PAGES
# ─────────────────────────────────────────────────────────────────────────────

def show_dashboard_overview(intermediary_type: str):
    st.header("📈 Compliance Dashboard Overview")
    stats = get_api_data("/graph/statistics")
    if not stats or stats.get("total_obligations", 0) == 0:
        st.warning("No obligations yet. Upload a circular first (📤 Upload Circular in sidebar).")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Obligations",  stats.get("total_obligations", 0))
    c2.metric("Active",             stats.get("active_obligations", 0))
    c3.metric("High Severity",      stats.get("high_severity_count", 0))
    c4.metric("Circulars Ingested", stats.get("circulars_ingested", 0))

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        ev = stats.get("evidence_gaps", {})
        fig = go.Figure(go.Bar(
            x=["Complete", "Partial", "Missing"],
            y=[ev.get("complete", 0), ev.get("partial", 0), ev.get("missing", 0)],
            marker_color=["#2ecc71", "#f39c12", "#e74c3c"]
        ))
        fig.update_layout(title="Evidence Status", xaxis_title="Status", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        active = stats.get("active_obligations", 0)
        sup    = stats.get("superseded_obligations", 0)
        if active + sup > 0:
            fig = go.Figure(go.Pie(
                labels=["Active", "Superseded"],
                values=[active, sup],
                marker_colors=["#3498db", "#95a5a6"]
            ))
            fig.update_layout(title="Obligation Status")
            st.plotly_chart(fig, use_container_width=True)


def show_search_obligations():
    st.header("🔍 Search Obligations")
    query = st.text_input("Search (e.g. 'trading window', 'margin', 'insider trading')")
    if query:
        results = get_api_data(f"/obligations/search?query={query}&semantic=true")
        items = results.get("results", [])
        if items:
            st.success(f"Found {len(items)} obligations")
            for obl in items:
                with st.expander(f"📌 {obl['title']} — {obl['severity'].upper()}"):
                    st.write(f"**Description:** {obl['description']}")
                    st.write(f"**Responsible:** {obl['responsible_party']}")
                    st.write(f"**Action:** {obl['required_action']}")
                    st.write(f"**Deadline:** {obl.get('deadline') or 'Not specified'}")
                    st.caption(f"Clause: {obl.get('clause_reference','—')}")
        else:
            st.info("No results found.")


def show_compliance_mapping(intermediary_type: str):
    st.header(f"📋 Compliance Mapping — {intermediary_type.replace('_',' ').title()}")
    mapping = get_api_data(f"/compliance/mapping/{intermediary_type}")
    if not mapping:
        st.info("No compliance data yet. Upload a circular first.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Applicable Obligations", mapping.get("applicable_obligations_count", 0))
    c2.metric("Not Applicable",         mapping.get("not_applicable_count", 0))
    c3.metric("Critical Gaps",          mapping.get("critical_gaps_count", 0))

    st.markdown("---")
    st.subheader("Priority Action Items")
    items = mapping.get("action_items", [])
    if items:
        df = pd.DataFrame([{
            "Priority":    item.get("priority", "normal").upper(),
            "Responsible": item.get("responsible_party", "TBD"),
            "Action":      item.get("action", "")[:60],
            "Deadline":    item.get("deadline", "TBD"),
        } for item in items[:15]])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No action items.")


def show_graph_analysis():
    st.header("🌐 Graph Analysis")
    stats = get_api_data("/graph/statistics")
    if stats:
        c1, c2, c3 = st.columns(3)
        c1.metric("Nodes",   stats.get("total_nodes", 0))
        c2.metric("Edges",   stats.get("total_edges", 0))
        c3.metric("Density", f"{stats.get('network_density', 0):.3f}")

    st.markdown("---")
    obl_id = st.text_input("Enter Obligation ID to see its dependencies")
    if obl_id:
        deps = get_api_data(f"/graph/dependencies/{obl_id}")
        if deps:
            c1, c2, c3 = st.columns(3)
            c1.metric("Direct Dependencies",  deps.get("dependency_count", 0))
            c2.metric("Direct Dependents",    deps.get("dependent_count", 0))
            c3.metric("Transitive Dependents",deps.get("transitive_dependent_count", 0))


def show_evidence_gaps(intermediary_type: str):
    st.header("⚠️ Evidence Gaps")

    # Use the flat /evidence/gaps endpoint
    data = get_api_data("/evidence/gaps")
    if not data:
        st.info("No evidence gap data. Upload a circular first.")
        return

    gaps = data.get("gaps", [])
    total = data.get("total_gaps", len(gaps))

    if not gaps:
        st.success("No evidence gaps — all obligations have complete evidence!")
        return

    st.metric("Total gaps", total)
    st.markdown("---")

    for g in gaps:
        sev   = g.get("severity", "medium")
        ev    = g.get("evidence_status", "red")
        icon  = "🔴" if ev == "red" else "🟡"
        s_tag = "🔴 HIGH" if sev == "high" else "🟡 MEDIUM" if sev == "medium" else "🟢 LOW"
        with st.expander(f"{icon} {g['title']} — {s_tag}"):
            st.write(f"**Obligation ID:** `{g['obligation_id']}`")
            st.write(f"**Circular:** {g['circular_id']}")
            st.write(f"**Evidence needed:** {', '.join(g.get('evidence_requirements') or ['—'])}")
            st.caption("Upload evidence via POST /api/v1/evidence/upload")


def show_impact_analysis():
    st.header("🔗 Impact Analysis")

    # List available obligation IDs to make it easy
    stats = get_api_data("/graph/statistics")
    total = stats.get("total_obligations", 0) if stats else 0
    if total == 0:
        st.info("No obligations in graph yet. Upload a circular first.")
        return

    st.caption(f"{total} obligations in graph. Enter an ID below to trace its downstream impact.")
    obl_id = st.text_input("Obligation ID", placeholder="e.g. SEBI_SURVEILLANCE_MC_2026_obl_0")

    if obl_id:
        impact = get_api_data(f"/graph/impact/{obl_id}")
        if impact:
            c1, c2, c3 = st.columns(3)
            c1.metric("Directly Affected",   len(impact.get("directly_affected", [])))
            c2.metric("Indirectly Affected",  len(impact.get("indirectly_affected", [])))
            c3.metric("Total Affected",
                      len(impact.get("directly_affected", [])) +
                      len(impact.get("indirectly_affected", [])))

            direct = impact.get("directly_affected", [])
            if direct:
                st.markdown("**Directly affected obligations:**")
                for d in direct[:10]:
                    st.markdown(f"- `{d}`")


if __name__ == "__main__":
    main()
