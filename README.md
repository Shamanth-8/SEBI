# RegGraph — Agentic Compliance System

> Transforms SEBI regulatory circulars into structured, auditable compliance obligations using a multi-agent AI pipeline.

**Problem Statement 2** — Agentic Compliance: From Regulatory Text to Operational Action

**Corpus:** SEBI Master Circular on Surveillance of Securities Market (38 pages)  
**Intermediaries:** Stockbroker · Depository · Listed Company · Investment Adviser · Fiduciary

---

## What it does

SEBI issues circulars in unstructured PDF format. Compliance teams manually read each one, figure out what changed, and update their checklists. RegGraph automates this end-to-end:

1. Upload a SEBI circular (PDF or text)
2. AI agents extract every obligation clause-by-clause
3. Semantic diff classifies each as NEW / MODIFIED / SUPERSEDED against existing obligations
4. Graph traversal propagates impact to all downstream dependent obligations
5. Compliance action items generated per intermediary type and per responsible role
6. Evidence gaps flagged — green (complete) / yellow (partial) / red (missing)
7. Every step timestamped in an audit trail

---

## Architecture

```
circular.pdf
     │
     ▼
┌─────────────────────────────────────────────────────┐
│               7-Step Agent Pipeline                 │
│                                                     │
│  1. PDF Extraction  (pdfplumber)                    │
│  2. Extraction Agent  ──► Claude/Mistral via        │
│     chunks circular        OpenRouter               │
│     extracts obligations                            │
│  3. Semantic Diff Agent ──► classifies NEW /        │
│     compares against        MODIFIED /              │
│     existing graph          SUPERSEDED              │
│  4. Graph Integration ──► NetworkX directed graph   │
│     adds nodes + edges      obligation_graph.pkl    │
│  5. Impact Propagation ──► BFS traversal            │
│     finds all downstream    affected obligations    │
│  6. Compliance Mapping ──► per intermediary type    │
│     action items per role   evidence gap detection  │
│  7. Audit + Metrics ──► audit_log.json              │
│     timestamps every step   metrics.json            │
└─────────────────────────────────────────────────────┘
     │
     ▼
FastAPI Backend (port 8000) + Streamlit Dashboard (port 8501)
```

---

## Project structure

```
.
├── backend/
│   └── app/
│       ├── agents/
│       │   ├── orchestrator.py        # 7-step pipeline coordinator
│       │   ├── extraction_agent.py    # LLM-based obligation extraction
│       │   ├── diff_agent.py          # semantic NEW/MODIFIED/SUPERSEDED
│       │   ├── impact_propagation.py  # BFS graph traversal
│       │   └── mapping_agent.py       # per-intermediary compliance mapping
│       ├── api/
│       │   ├── circulars.py           # upload + process circular
│       │   ├── obligations.py         # search + query obligations
│       │   ├── compliance.py          # compliance dashboard per intermediary
│       │   ├── graph.py               # graph stats + dependency analysis
│       │   ├── evidence.py            # evidence upload + gap detection
│       │   └── audit_api.py           # audit trail + pipeline metrics
│       ├── graph/
│       │   └── obligation_graph.py    # NetworkX graph wrapper
│       ├── retrieval/
│       │   └── faiss_search.py        # semantic similarity search
│       ├── audit.py                   # audit logging to data/audit_log.json
│       ├── metrics.py                 # pipeline performance metrics
│       ├── anthropic_adapter.py       # OpenRouter ↔ Anthropic interface
│       ├── config.py                  # env-based configuration
│       └── main.py                    # FastAPI app + router registration
├── frontend/
│   └── dashboard.py                   # Streamlit UI
├── data/                              # auto-created, gitignored
│   ├── obligation_graph.pkl           # persisted NetworkX graph
│   ├── faiss_index                    # semantic search index
│   ├── audit_log.json                 # timestamped audit trail
│   └── metrics.json                   # pipeline performance records
├── circular.pdf                       # SEBI Master Circular (Surveillance)
├── circular_extracted.json            # pre-extracted text from circular.pdf
├── sebi_obligations_dataset.json      # 40 sample SEBI obligations
├── extract_circular.py                # extract text from any PDF
├── generate_demo_report.py            # generates demo_report.html
├── demo_report.html                   # visual demo report
├── requirements.txt
└── .env.example
```

---

## Quickstart

### 1. Clone and set up

```bash
git clone https://github.com/Shamanth-8/SEBI.git
cd SEBI

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API key

```bash
cp .env.example .env
# Edit .env and set your OpenRouter key:
# OPENROUTER_API_KEY=sk-or-v1-...
# OPENROUTER_MODEL=mistralai/mistral-7b-instruct:free   # free tier
# OPENROUTER_MODEL=anthropic/claude-3-sonnet             # best results
```

Get a free key at [openrouter.ai](https://openrouter.ai)

### 3. Start the backend

```bash
PYTHONPATH=backend venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Start the dashboard

```bash
venv/bin/streamlit run frontend/dashboard.py --server.port 8501
```

### 5. Open in browser

| URL | Purpose |
|-----|---------|
| `http://localhost:8501` | Main dashboard |
| `http://localhost:8000/docs` | Swagger API docs |
| `demo_report.html` | Open locally — full pipeline report |

---

## Running the pipeline on circular.pdf

```bash
# Option A — via API (recommended)
python3 - << 'EOF'
import json, httpx
data = json.load(open("circular_extracted.json"))
resp = httpx.post("http://localhost:8000/api/v1/circulars/upload",
    json={"circular_id": data["circular_id"], "title": data["title"],
          "document_text": data["full_text"], "intermediary_types": data["intermediary_types"]},
    timeout=600)
print(resp.json())
EOF

# Option B — extract from a new PDF first
python3 extract_circular.py   # edit path inside the script
```

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/circulars/upload` | Upload circular text → full pipeline |
| POST | `/api/v1/circulars/upload-file` | Upload PDF/TXT file |
| GET | `/api/v1/circulars/{id}` | Get obligations for a circular |
| GET | `/api/v1/obligations/search?query=` | Semantic search |
| GET | `/api/v1/obligations/{id}` | Get obligation details |
| GET | `/api/v1/graph/statistics` | Graph-level stats |
| GET | `/api/v1/graph/impact/{id}` | Dependency impact chain |
| GET | `/api/v1/compliance/dashboard/{type}` | Per-intermediary dashboard |
| POST | `/api/v1/evidence/upload` | Upload evidence doc + match |
| GET | `/api/v1/evidence/gaps` | All obligations missing evidence |
| GET | `/api/v1/audit/trail` | Full timestamped audit log |
| GET | `/api/v1/audit/metrics/latest` | Latest pipeline performance |

Full interactive docs: `http://localhost:8000/docs`

---

## What was extracted from circular.pdf

**Circular:** SEBI Master Circular on Surveillance of Securities Market  
**Reference:** HO/43/15/12(3)2025-ISD-POD2/I/11734/2026  
**Issued:** March 23, 2023 · **Last updated:** May 15, 2026  
**Pages:** 38 · **Characters:** 52,844

Sample obligations extracted by the pipeline:
- Compliance with SCRA, SEBI Act by Stock Exchanges and Clearing Corporations — **HIGH**
- Compliance with SEBI Act and Depositories Act by Depositories — **HIGH**
- Prevent Circulation of Unauthenticated News or Rumours — **HIGH**
- Trading Window Closure obligations for Designated Persons — **HIGH**
- Financial Disincentives for Surveillance-Related Lapses at MIIs — **HIGH**

---

## Problem Statement compliance

| Requirement | Status |
|-------------|--------|
| Regulatory text → operational action | ✅ Extraction Agent + Mapping Agent |
| Works on SEBI circulars | ✅ Tested on 38-page Master Circular |
| Specifies intermediary category | ✅ Stockbroker, Depository, Listed Co., Investment Adviser |
| Specifies regulatory corpus | ✅ SEBI Master Circular on Surveillance |
| Concrete regulatory scenario demo | ✅ demo_report.html |
| Dynamic regulatory translation | ✅ Diff Agent: NEW / MODIFIED / SUPERSEDED |
| Ongoing compliance management | ✅ Evidence gaps, per-intermediary dashboards |
| Auditability | ✅ Every step logged with timestamp + clause reference |
| Evidence mapping | ✅ `/api/v1/evidence/upload` — keyword match |
| Measurable performance | ✅ metrics.json — time per step, obligations/page |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| LLM | Claude (Anthropic) or Mistral via OpenRouter |
| Backend | FastAPI + Uvicorn |
| Dashboard | Streamlit |
| Graph | NetworkX (directed graph, BFS traversal) |
| Semantic search | FAISS |
| PDF parsing | pdfplumber |
| Data models | Pydantic v2 |
| Persistence | Pickle + JSON |

---

## Notes

- The `data/` folder is gitignored — it's created automatically on first run
- `.env` is gitignored — never commit your API key
- Use `mistralai/mistral-7b-instruct:free` for testing (free but less accurate)
- Use `anthropic/claude-3-sonnet` for production (best extraction quality)
