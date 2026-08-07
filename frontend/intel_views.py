"""
Document Intelligence and Chat views for the RegGraph dashboard.

Kept in its own module so dashboard.py stays navigable; it declares its own tiny
HTTP helpers rather than importing from dashboard.py, which would be circular.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import plotly.graph_objects as go
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

# ── Chart tokens ─────────────────────────────────────────────────────────────
# Categorical hues stepped for this dashboard's dark surface (#131826) and
# validated as a set: lightness band, chroma floor, CVD separation, normal-vision
# separation and 3:1 contrast all pass. Assigned in fixed order, never cycled.
CAT = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"]

# Status colours are reserved for severity and never reused as "series 4".
SEV_COLOR = {"high": "#F87171", "medium": "#FBBF24", "low": "#34D399"}
SEV_ORDER = ["high", "medium", "low"]

# Single hue for magnitude (sequential role) — the app's accent.
SEQ = "#8B5CF6"
SEQ_MUTED = "rgba(139,92,246,0.35)"

INK = "#E2E8F0"
INK_MUTED = "#94A3B8"
GRID = "#1E293B"
SURFACE = "#131826"

LEVEL_STYLE = {
    "success": ("✅", "#34D399"),
    "warning": ("⚠️", "#FBBF24"),
    "info": ("ℹ️", "#60A5FA"),
    "error": ("❌", "#F87171"),
}


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _get(endpoint: str, timeout: float = 20.0) -> Dict:
    try:
        r = httpx.get(f"{API_BASE_URL}{endpoint}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _post(endpoint: str, payload: Dict, timeout: float = 120.0) -> Dict:
    try:
        r = httpx.post(f"{API_BASE_URL}{endpoint}", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _post_file(endpoint: str, files, data, timeout: float = 180.0) -> Dict:
    try:
        r = httpx.post(f"{API_BASE_URL}{endpoint}", files=files, data=data, timeout=timeout)
        if r.status_code != 200:
            try:
                return {"error": r.json().get("detail", r.text[:300])}
            except Exception:
                return {"error": r.text[:300]}
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _err(d: Dict) -> bool:
    return not isinstance(d, dict) or "error" in d


# ── Chart helpers ────────────────────────────────────────────────────────────

def _style(fig: go.Figure, height: int = 280, showlegend: bool = False,
           xtitle: str = "", ytitle: str = "") -> go.Figure:
    """Recessive grid and axes, transparent surface, text in ink tokens."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=16, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK, size=12, family="Inter, system-ui, sans-serif"),
        showlegend=showlegend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=INK_MUTED, size=11)),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=GRID,
                        font=dict(color=INK, size=12)),
        xaxis_title=xtitle, yaxis_title=ytitle,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(color=INK_MUTED, size=11),
                     title_font=dict(color=INK_MUTED, size=11))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(color=INK_MUTED, size=11),
                     title_font=dict(color=INK_MUTED, size=11))
    return fig


def _hbar(labels: List[str], values: List[float], colors, hover: str,
          height: int = 280, text: Optional[List[str]] = None) -> go.Figure:
    """Horizontal bars, largest at top, 4px rounded data-ends on the baseline."""
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors, cornerradius=4,
                    line=dict(color=SURFACE, width=2)),   # 2px surface gap
        text=text if text is not None else [f"{v:g}" for v in values],
        textposition="outside", textfont=dict(color=INK_MUTED, size=11),
        hovertemplate=hover, cliponaxis=False,
    ))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(showgrid=True, rangemode="tozero")
    return _style(fig, height=height)


def _vbar(labels: List[str], values: List[float], colors, hover: str,
          height: int = 260) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker=dict(color=colors, cornerradius=4, line=dict(color=SURFACE, width=2)),
        text=[f"{v:g}" for v in values], textposition="outside",
        textfont=dict(color=INK_MUTED, size=11),
        hovertemplate=hover, cliponaxis=False,
    ))
    fig.update_yaxes(rangemode="tozero")
    return _style(fig, height=height)


def _sequential(values: List[float]) -> List[str]:
    """One hue, opacity carrying magnitude — never a rainbow for a magnitude."""
    if not values:
        return []
    hi = max(values) or 1
    return [f"rgba(139,92,246,{0.35 + 0.6 * (v / hi):.2f})" for v in values]


# ── Small HTML pieces ────────────────────────────────────────────────────────

def _kpi_row(items: List[tuple]) -> str:
    cards = "".join(
        f'<div class="kpi-card"><div class="kpi-val" style="color:{color}">{val}</div>'
        f'<div class="kpi-lbl">{label}</div></div>'
        for val, label, color in items
    )
    return f'<div class="kpi-row">{cards}</div>'


def _findings_html(findings: List[Dict]) -> str:
    rows = []
    for f in findings:
        icon, color = LEVEL_STYLE.get(f.get("level", "info"), LEVEL_STYLE["info"])
        rows.append(
            f'<div style="display:flex;gap:10px;padding:9px 0;border-bottom:1px solid {GRID}">'
            f'<div style="font-size:0.95rem">{icon}</div>'
            f'<div><div style="font-weight:600;color:{color};font-size:0.88rem">'
            f'{f.get("title","")}</div>'
            f'<div style="color:{INK_MUTED};font-size:0.82rem;line-height:1.5">'
            f'{f.get("detail","")}</div></div></div>'
        )
    return f'<div class="rg-card">{"".join(rows)}</div>'


def _recognition_card(rec: Dict) -> str:
    verdict = rec.get("verdict", "—")
    circ = rec.get("circular_confidence", 0)
    is_circ = rec.get("is_circular", False)
    novel = rec.get("is_novel_topic", False)
    color = "#34D399" if (is_circ and not novel) else ("#FBBF24" if is_circ else "#F87171")
    badge = "RECOGNISED" if is_circ and not novel else ("NOVEL TOPIC" if is_circ else "REJECTED")
    fam = (rec.get("family_label") or rec.get("family") or "—")
    return f"""
<div class="rg-card" style="border-color:{color}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap">
    <div>
      <span style="font-size:0.68rem;letter-spacing:1px;color:{color};font-weight:700;
                   border:1px solid {color};padding:2px 8px;border-radius:20px">{badge}</span>
      <div style="font-size:1.05rem;font-weight:650;color:{INK};margin-top:8px">{verdict}</div>
      <div style="color:{INK_MUTED};font-size:0.82rem;margin-top:4px">
        Closest family: <b style="color:{INK}">{fam}</b> ·
        {rec.get("windows_analysed", 0)} text windows analysed ·
        novelty {rec.get("novelty", 0):.0%}
      </div>
    </div>
    <div style="text-align:right">
      <div style="font-size:1.8rem;font-weight:700;color:{color};line-height:1">{circ:.0%}</div>
      <div style="font-size:0.7rem;color:{INK_MUTED};text-transform:uppercase;letter-spacing:0.5px">
        is a circular</div>
    </div>
  </div>
</div>"""


# ── Charts ───────────────────────────────────────────────────────────────────

def _family_chart(rec: Dict):
    scores = rec.get("family_scores") or {}
    if not scores:
        return None
    items = sorted(scores.items(), key=lambda kv: -kv[1])
    labels = [k.replace("_", " ").title() for k, _ in items]
    values = [round(v * 100, 1) for _, v in items]
    # Magnitude of one quantity across categories → one hue, not eight.
    return _hbar(labels, values, _sequential(values),
                 "%{y}<br>match %{x:.1f}%<extra></extra>",
                 height=40 + 34 * len(labels),
                 text=[f"{v:.0f}%" for v in values])


def _severity_chart(dist: Dict):
    present = [s for s in SEV_ORDER if dist.get(s)]
    if not present:
        return None
    values = [dist[s] for s in present]
    return _hbar([s.title() for s in present], values,
                 [SEV_COLOR[s] for s in present],
                 "%{y} severity<br>%{x} obligations<extra></extra>",
                 height=40 + 40 * len(present))


def _simple_dist_chart(dist: Dict, hover: str, height_per: int = 34):
    items = [(k, v) for k, v in dist.items() if v]
    if not items:
        return None
    items.sort(key=lambda kv: -kv[1])
    labels = [str(k).replace("_", " ").title() for k, _ in items]
    values = [v for _, v in items]
    colors = [CAT[i % len(CAT)] for i in range(len(items))]
    return _hbar(labels, values, colors, hover, height=50 + height_per * len(items))


def _deadline_dots(calendar: List[Dict]):
    """Fixed-date deadlines on a days-remaining axis, coloured by severity."""
    fixed = [c for c in calendar if c.get("days_remaining") is not None][:14]
    if not fixed:
        return None
    fixed.sort(key=lambda c: c["days_remaining"])
    fig = go.Figure()
    for sev in SEV_ORDER:
        pts = [c for c in fixed if c.get("severity") == sev]
        if not pts:
            continue
        fig.add_trace(go.Scatter(
            x=[p["days_remaining"] for p in pts],
            y=[p["title"][:46] for p in pts],
            mode="markers", name=sev.title(),
            marker=dict(size=11, color=SEV_COLOR[sev],
                        line=dict(color=SURFACE, width=2)),   # 2px surface ring
            hovertemplate="%{y}<br>%{x} days remaining<extra>" + sev + "</extra>",
        ))
    fig.add_vline(x=0, line_color="#F87171", line_width=1, line_dash="dot")
    fig.update_yaxes(autorange="reversed")
    return _style(fig, height=60 + 30 * len(fixed), showlegend=True,
                  xtitle="days remaining")


# ── Insight blocks (reused on the Upload page) ───────────────────────────────

def render_pre_ai_block(pre_ai: Dict, compact: bool = False) -> None:
    """Deterministic analysis: recognition, metrics, findings, charts."""
    rec = pre_ai.get("recognition") or {}
    if rec:
        st.markdown(_recognition_card(rec), unsafe_allow_html=True)

    m = pre_ai.get("summary_metrics") or {}
    if m:
        st.markdown(_kpi_row([
            (m.get("obligations_detected", 0), "Obligations", SEQ),
            (m.get("high_severity", 0), "High severity", SEV_COLOR["high"]),
            (m.get("with_deadline", 0), "With deadline", INK),
            (m.get("without_deadline", 0), "No deadline", SEV_COLOR["medium"]),
            (f"{m.get('mean_confidence', 0):.2f}", "Mean confidence", INK),
        ]), unsafe_allow_html=True)

    findings = pre_ai.get("findings") or []
    if findings:
        st.markdown("##### What the local model found")
        st.markdown(_findings_html(findings), unsafe_allow_html=True)

    if compact:
        return

    dist = pre_ai.get("distributions") or {}
    c1, c2 = st.columns(2)
    with c1:
        fig = _severity_chart(dist.get("severity") or {})
        if fig:
            st.caption("Severity mix")
            st.plotly_chart(fig, use_container_width=True)
        fig = _simple_dist_chart(dist.get("intermediary_types") or {},
                                 "%{y}<br>%{x} obligations<extra></extra>")
        if fig:
            st.caption("Obligations by intermediary type")
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = _simple_dist_chart(dist.get("deadline_type") or {},
                                 "%{y}<br>%{x} obligations<extra></extra>")
        if fig:
            st.caption("Deadline type")
            st.plotly_chart(fig, use_container_width=True)
        fig = _simple_dist_chart(dist.get("responsible_parties") or {},
                                 "%{y}<br>%{x} obligations<extra></extra>")
        if fig:
            st.caption("Accountable roles")
            st.plotly_chart(fig, use_container_width=True)

    cal = pre_ai.get("deadline_calendar") or []
    fig = _deadline_dots(cal)
    if fig:
        st.caption("Dated deadlines — days remaining (negative = overdue)")
        st.plotly_chart(fig, use_container_width=True)


def render_ai_block(ai: Dict) -> None:
    """The LLM layer, clearly labelled as such and never silently empty."""
    if not ai:
        st.info("No AI insight layer was generated for this run.")
        return
    if not ai.get("available"):
        st.warning(
            f"🤖 AI insight layer unavailable — showing the local analysis only.\n\n"
            f"`{str(ai.get('error'))[:300]}`"
        )
        return

    ins = ai.get("insights") or {}
    st.markdown(
        f'<div style="font-size:0.72rem;color:{INK_MUTED};text-transform:uppercase;'
        f'letter-spacing:0.6px;margin-bottom:6px">Generated by {ai.get("model","LLM")} '
        f'· grounded on the numbers above</div>', unsafe_allow_html=True)

    if ins.get("executive_summary"):
        st.markdown(
            f'<div class="rg-card" style="border-color:{SEQ}">'
            f'<div style="font-size:0.93rem;line-height:1.65;color:{INK}">'
            f'{ins["executive_summary"]}</div></div>', unsafe_allow_html=True)

    risks = ins.get("key_risks") or []
    if risks:
        st.markdown("##### ⚠️ Key risks")
        for r in risks:
            if isinstance(r, dict):
                ids = ", ".join(r.get("obligation_ids") or [])
                st.markdown(
                    f'<div class="rg-card" style="padding:10px 14px;margin-bottom:6px">'
                    f'<b style="color:{SEV_COLOR["high"]}">{r.get("risk","")}</b><br>'
                    f'<span style="color:{INK_MUTED};font-size:0.84rem">{r.get("why","")}</span>'
                    + (f'<br><span style="color:{INK_MUTED};font-size:0.72rem">{ids}</span>'
                       if ids else "")
                    + '</div>', unsafe_allow_html=True)
            else:
                st.markdown(f"- {r}")

    c1, c2 = st.columns(2)
    with c1:
        if ins.get("first_30_days"):
            st.markdown("##### 🚀 First 30 days")
            for a in ins["first_30_days"]:
                st.markdown(f"- {a}")
    with c2:
        if ins.get("ambiguities"):
            st.markdown("##### 🤔 Ambiguities")
            for a in ins["ambiguities"]:
                st.markdown(f"- {a}")
        if ins.get("questions_for_the_regulator"):
            st.markdown("##### ❓ Worth raising with SEBI")
            for q in ins["questions_for_the_regulator"]:
                st.markdown(f"- {q}")

    if ins.get("effort_view"):
        st.caption(f"**Effort:** {ins['effort_view']}")


# ── Page: Document Intelligence ──────────────────────────────────────────────

def render_intelligence_page(intermediary_type: str) -> None:
    st.markdown("## 🧠 Document Intelligence")
    st.markdown(
        f'<p style="color:{INK_MUTED};margin-top:-8px">Runs the locally trained model on any '
        'PDF — recognition, obligations and charts — with no LLM call and no API quota spent. '
        'This is what the pipeline sees <i>before</i> the AI layer.</p>',
        unsafe_allow_html=True)

    model = _get("/intel/model", timeout=15)
    if _err(model):
        st.error(f"Backend unreachable: {model.get('error')}")
        return
    if not model.get("trained"):
        st.error("No trained model found.")
        st.code("python scripts/generate_corpus.py\npython scripts/train_model.py", language="bash")
        return

    tab_analyze, tab_model = st.tabs(["🔬 Analyse a document", "📊 Model card & corpus"])

    with tab_analyze:
        _render_analyze_tab(intermediary_type)
    with tab_model:
        _render_model_tab(model)


def _render_analyze_tab(intermediary_type: str) -> None:
    up = st.file_uploader("Drop any PDF or text file", type=["pdf", "txt"],
                          key="intel_uploader")
    threshold = st.slider(
        "Obligation threshold", 0.30, 0.90, 0.55, 0.05,
        help="Model probability above which a sentence counts as an obligation. "
             "Lower catches more and admits more noise.")

    col_a, col_b = st.columns([3, 1])
    with col_a:
        run = st.button("🔬 Analyse locally", type="primary", use_container_width=True,
                        disabled=up is None)
    with col_b:
        if st.button("🗑 Clear", use_container_width=True):
            st.session_state.pop("intel_result", None)
            st.rerun()

    if run and up is not None:
        with st.spinner("Running the local model…"):
            result = _post_file(
                "/intel/analyze-file",
                files={"file": (up.name, up.getvalue(), "application/pdf")},
                data={"circular_id": up.name.rsplit(".", 1)[0][:60],
                      "title": up.name,
                      "intermediary_types": intermediary_type,
                      "threshold": str(threshold)},
            )
        if _err(result):
            st.error(f"Analysis failed: {result.get('error')}")
            return
        st.session_state["intel_result"] = result
        st.toast("Local analysis complete", icon="🧠")

    result = st.session_state.get("intel_result")
    if not result:
        st.info("Upload a document to analyse. Try `data/corpus/holdout/` for circulars the "
                "model was never trained on, or `data/corpus/negative/` for documents it "
                "should reject.")
        return

    prof = result.get("document_profile") or {}
    st.markdown(_kpi_row([
        (prof.get("pages", 0) or "—", "Pages", INK),
        (f'{prof.get("words", 0):,}', "Words", INK),
        (prof.get("sentences", 0), "Sentences", INK),
        (f'{prof.get("reading_time_minutes", 0)} min', "Manual read time", INK_MUTED),
        (sum((prof.get("mandatory_language") or {}).values()), "Mandatory markers", SEQ),
    ]), unsafe_allow_html=True)

    render_pre_ai_block(result)

    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    _render_obligations_table(result)
    _render_secondary_charts(result)


def _render_obligations_table(result: Dict) -> None:
    obls = result.get("obligations_preview") or []
    diag = result.get("diagnostics") or {}
    if not obls:
        st.warning("The model found no obligations in this document.")
        return

    st.markdown(f"### 📋 Detected obligations ({len(obls)})")
    st.caption(
        f"From {diag.get('sentences_considered', 0)} candidate sentences at threshold "
        f"{diag.get('threshold', 0.55)} · model v{diag.get('model_version', '?')}")

    for o in obls[:40]:
        sev = o.get("severity", "medium")
        conf = o.get("confidence", 0)
        with st.expander(
            f"[{sev.upper()}] {o.get('title','')[:95]}  ·  confidence {conf:.2f}"
        ):
            st.markdown(f"**Clause:** `{o.get('clause_reference','')[:200]}`")
            st.markdown(f"**Text:** {o.get('description','')}")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Owner**\n\n{o.get('responsible_party','—')}")
            c2.markdown(f"**Deadline**\n\n{o.get('deadline') or '—'} "
                        f"({o.get('deadline_type','—')})")
            c3.markdown("**Applies to**\n\n" + ", ".join(o.get("intermediary_types") or []))
            st.markdown("**Evidence required:** " +
                        ", ".join(o.get("evidence_requirements") or []))
            st.caption(o.get("rationale", ""))

            if st.button("Why did the model say this?", key=f"why_{o['obligation_id']}"):
                exp = _post("/intel/explain", {"sentence": o.get("description", ""),
                                               "head": "obligation_clf", "top_k": 8})
                if _err(exp):
                    st.error(exp.get("error"))
                else:
                    contribs = exp.get("contributions") or []
                    labels = [c["feature"][:38] for c in contribs]
                    values = [c["contribution"] for c in contribs]
                    colors = [SEV_COLOR["low"] if v > 0 else SEV_COLOR["high"] for v in values]
                    fig = _hbar(labels, values, colors,
                                "%{y}<br>contribution %{x:.3f}<extra></extra>",
                                height=40 + 30 * len(labels),
                                text=[f"{v:+.2f}" for v in values])
                    st.caption("Signed contribution of each n-gram to the decision "
                               "function (green supports, red opposes)")
                    st.plotly_chart(fig, use_container_width=True)

    rejected = diag.get("rejected") or []
    if rejected:
        with st.expander(f"🔍 {len(rejected)} borderline sentences the model rejected"):
            st.caption("Scored between 0.30 and the threshold — review these when recall matters "
                       "more than precision.")
            for r in rejected:
                st.markdown(f"- `{r['probability']:.2f}` · {r['text']}")


def _render_secondary_charts(result: Dict) -> None:
    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    st.markdown("### 📈 Document structure")

    c1, c2 = st.columns(2)
    with c1:
        rec = result.get("recognition") or {}
        fig = _family_chart(rec)
        if fig:
            st.caption("Which trained circular family this resembles")
            st.plotly_chart(fig, use_container_width=True)

        conf = (result.get("distributions") or {}).get("confidence_buckets") or {}
        if conf:
            labels = list(conf.keys())
            values = [conf[k] for k in labels]
            st.caption("Model confidence distribution")
            st.plotly_chart(
                _vbar(labels, values, _sequential(values),
                      "confidence %{x}<br>%{y} obligations<extra></extra>"),
                use_container_width=True)

    with c2:
        sections = result.get("sections") or []
        top = sorted(sections, key=lambda s: -s.get("mandatory_sentences", 0))[:10]
        if top:
            labels = [s["section"][:42] for s in top]
            values = [s.get("mandatory_sentences", 0) for s in top]
            st.caption("Mandatory sentences per section")
            st.plotly_chart(
                _hbar(labels, values, _sequential(values),
                      "%{y}<br>%{x} mandatory sentences<extra></extra>",
                      height=50 + 32 * len(labels)),
                use_container_width=True)

        kws = (result.get("keywords") or [])[:12]
        if kws:
            labels = [k["term"][:34] for k in kws]
            values = [k["count"] for k in kws]
            st.caption("Most frequent terms")
            st.plotly_chart(
                _hbar(labels, values, _sequential(values),
                      "%{y}<br>%{x} occurrences<extra></extra>",
                      height=50 + 30 * len(labels)),
                use_container_width=True)

    prof = result.get("document_profile") or {}
    refs = prof.get("circular_references") or []
    legal = prof.get("legal_references") or []
    if refs or legal:
        with st.expander("🔗 References found in the document"):
            if refs:
                st.markdown("**Other circulars:** " + ", ".join(f"`{r}`" for r in refs))
            if legal:
                st.markdown("**Legal provisions:** " + ", ".join(f"`{r}`" for r in legal))


def _render_model_tab(model: Dict) -> None:
    card = model.get("card") or {}
    corpus = card.get("corpus") or {}
    ev = card.get("evaluation") or {}

    st.markdown(f"#### Model v{model.get('version','?')} · {card.get('algorithm','—')}")
    st.caption(f"Trained {card.get('trained_at','—')}")

    st.markdown(_kpi_row([
        (corpus.get("circulars_total", 0), "Training circulars", SEQ),
        (f'{corpus.get("labelled_sentences", 0):,}', "Labelled sentences", INK),
        (corpus.get("obligation_sentences", 0), "Obligation examples", INK),
        (corpus.get("negative_documents", 0), "Negative documents", INK_MUTED),
        (corpus.get("template_bank_size", 0), "Clause templates", INK_MUTED),
    ]), unsafe_allow_html=True)

    st.markdown("##### Held-out evaluation")
    st.caption(ev.get("protocol", ""))

    rows = []
    for head, label in [("obligation_clf", "Is it an obligation?"),
                        ("severity_clf", "Severity"),
                        ("category_clf", "Regulatory theme"),
                        ("deadline_clf", "Deadline type")]:
        r = ev.get(head) or {}
        if not r:
            continue
        score = r.get("f1", r.get("accuracy", 0))
        metric = "F1" if "f1" in r else "accuracy"
        rows.append({"Head": label, "Metric": metric, "Score": round(score, 3),
                     "Train n": r.get("n_train", 0), "Test n": r.get("n_test", 0)})
    if rows:
        labels = [r["Head"] for r in rows]
        values = [r["Score"] * 100 for r in rows]
        st.plotly_chart(
            _hbar(labels, values, _sequential(values),
                  "%{y}<br>%{x:.1f}%<extra></extra>",
                  height=50 + 40 * len(labels),
                  text=[f"{v:.0f}%" for v in values]),
            use_container_width=True)
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if card.get("caveat"):
        st.warning(f"**Caveat:** {card['caveat']}")

    dists = card.get("label_distribution") or {}
    if dists:
        cols = st.columns(len(dists))
        for col, (name, dist) in zip(cols, dists.items()):
            with col:
                fig = _simple_dist_chart(dist, "%{y}<br>%{x} examples<extra></extra>")
                if fig:
                    st.caption(f"Training labels — {name.replace('_',' ')}")
                    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="rg-divider">', unsafe_allow_html=True)
    st.markdown("##### Training corpus")
    corpus_files = _get("/intel/corpus", timeout=10)
    if _err(corpus_files) or not corpus_files.get("generated"):
        st.info("Corpus PDFs not generated yet — run `python scripts/generate_corpus.py`.")
        return
    c1, c2, c3 = st.columns(3)
    for col, key, title, note in [
        (c1, "demo_circulars", "📄 Demo circulars", "the corpus the model learned from"),
        (c2, "holdout_circulars", "🧪 Holdout", "never seen during training"),
        (c3, "negative_documents", "🚫 Negatives", "should be rejected as non-circulars"),
    ]:
        with col:
            files = corpus_files.get(key) or []
            st.markdown(f"**{title}** ({len(files)})")
            st.caption(note)
            for f in files:
                st.markdown(f'<div style="font-size:0.76rem;color:{INK_MUTED}">'
                            f'{f["name"]} · {f["size_kb"]} KB</div>', unsafe_allow_html=True)


# ── Page: Chat ───────────────────────────────────────────────────────────────

def render_chat_page() -> None:
    st.markdown("## 💬 Ask about a circular")
    st.markdown(
        f'<p style="color:{INK_MUTED};margin-top:-8px">Questions are answered from passages '
        'retrieved out of the circular itself, with the clause shown alongside — so every '
        'answer can be checked against the source.</p>', unsafe_allow_html=True)

    listing = _get("/chat/circulars", timeout=15)
    if _err(listing):
        st.error(f"Backend unreachable: {listing.get('error')}")
        return

    circulars = listing.get("circulars") or []
    if not circulars:
        st.info("No circular has been indexed yet. Process one on the **Upload Circular** page, "
                "then come back here.")
        return

    options = {f'{c["title"][:60] or c["circular_id"]}  ·  {c["circular_id"][:40]}': c
               for c in circulars}
    label = st.selectbox("Circular", list(options.keys()), key="chat_circular_select")
    chosen = options[label]
    circular_id = chosen["circular_id"]

    st.caption(f'{chosen["passages"]} indexed passages · {chosen["characters"]:,} characters')

    history_key = f"chat_history::{circular_id}"
    history: List[Dict] = st.session_state.setdefault(history_key, [])

    # Starter questions, built from what this circular actually contains
    if not history:
        sugg = _get(f"/chat/suggestions/{circular_id}", timeout=10)
        if not _err(sugg):
            st.markdown("###### Try asking")
            cols = st.columns(2)
            for i, q in enumerate((sugg.get("suggestions") or [])[:6]):
                with cols[i % 2]:
                    if st.button(q, key=f"sugg_{circular_id}_{i}", use_container_width=True):
                        st.session_state[f"pending_q::{circular_id}"] = q
                        st.rerun()

    for turn in history:
        with st.chat_message("user" if turn["role"] == "user" else "assistant"):
            st.markdown(turn["content"])
            if turn.get("sources"):
                with st.expander(f"📎 {len(turn['sources'])} source passages"):
                    for s in turn["sources"]:
                        tag = f'`{s["passage_id"]}` · {s["section"][:60]} · '\
                              f'relevance {s.get("score", 0):.2f}'
                        st.markdown(tag)
                        st.markdown(f'> {s["excerpt"]}')
            if turn.get("mode") == "extractive":
                st.caption("⚠️ Answered without the language model — passages quoted verbatim.")

    pending = st.session_state.pop(f"pending_q::{circular_id}", None)
    question = st.chat_input("Ask about this circular…") or pending

    if question:
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching the circular…"):
                resp = _post("/chat/ask", {
                    "question": question,
                    "circular_id": circular_id,
                    "history": [{"role": t["role"], "content": t["content"]}
                                for t in history[-6:]],
                }, timeout=180.0)
            if _err(resp):
                answer = f"❌ Chat failed: {resp.get('error')}"
                st.error(answer)
                history.append({"role": "assistant", "content": answer})
            else:
                st.markdown(resp["answer"])
                if resp.get("sources"):
                    with st.expander(f"📎 {len(resp['sources'])} source passages"):
                        for s in resp["sources"]:
                            st.markdown(f'`{s["passage_id"]}` · {s["section"][:60]} · '
                                        f'relevance {s.get("score", 0):.2f}')
                            st.markdown(f'> {s["excerpt"]}')
                if resp.get("mode") == "extractive":
                    st.caption("⚠️ Answered without the language model — "
                               f"passages quoted verbatim. ({str(resp.get('llm_error'))[:120]})")
                history.append({
                    "role": "assistant", "content": resp["answer"],
                    "sources": resp.get("sources"), "mode": resp.get("mode"),
                })
        st.session_state[history_key] = history

    if history and st.button("🗑 Clear conversation"):
        st.session_state[history_key] = []
        st.rerun()
