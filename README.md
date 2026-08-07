# RegGraph — Agentic Compliance System

> Transforms SEBI regulatory circulars into structured, auditable compliance obligations using a multi-agent AI pipeline.

**Problem Statement 2** — Agentic Compliance: From Regulatory Text to Operational Action

### Regulatory corpus and intermediary category

| | |
|---|---|
| **Primary intermediary** | **Stockbroker** (also supports depository, RTA, investment adviser, listed company, portfolio manager) |
| **Primary corpus** | **SEBI Master Circular for Stock Brokers** — 399 pages, June 2025 |
| **Secondary corpus** | SEBI Master Circular for Investment Advisers (99 pages, Feb 2026) · SEBI Master Circular on Surveillance of Securities Market (38 pages) |
| **Source** | Fetched live from sebi.gov.in — `python scripts/fetch_sebi_corpus.py` |

Both corpora PS2 suggests are downloaded by that script, so the corpus is
reproducible rather than a file that happened to be on disk.

A separate **synthetic corpus of 5 SEBI-format circulars** (`data/corpus/`) provides
the *labelled training data* for the local classifier — every clause carries
ground-truth labels by construction. It is training data, not the regulatory
corpus, and the model is scored on documents held out of it.

### Measured performance

| Test | Result |
|---|---|
| Obligation extraction, circulars **held out of training** | precision **1.00** · recall **0.93** |
| Non-circular documents (contract, press release, manual, paper) | rejected at **2–3%** confidence |
| SEBI Master Circular for Stock Brokers (399 pp, unseen) | **1,391** obligations from 5,151 sentences · 7s |
| SEBI Master Circular for Investment Advisers (99 pp, unseen) | **238** obligations · 1s |
| Regulatory-change scenario (amendment vs circular in force) | 2 NEW · 7 MODIFIED detected, with the changed field named |
| Full pipeline with the LLM provider **down** | still returns every obligation |

Reproduce with `python scripts/evaluate_model.py` and `python scripts/demo_scenario.py`.

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
│  0. LOCAL MODEL  (no network, ~1s)                  │
│     recognise document ──► is this a SEBI circular? │
│     classify sentences     which family? novel?     │
│     extract obligations    severity · deadline ·    │
│     deterministic insights owner · evidence         │
│                                                     │
│  ── everything below enriches these results ──      │
│                                                     │
│  1. PDF Extraction  (pdfplumber)                    │
│  2. Extraction Agent  ──► LLM via OpenRouter,       │
│     merged with the local  agreement raises         │
│     model's obligations    confidence               │
│  3. Semantic Diff Agent ──► NEW / MODIFIED /        │
│     LLM, falling back to    SUPERSEDED, naming      │
│     lexical TF-IDF diff     the changed field       │
│  4. Graph Integration ──► NetworkX directed graph   │
│  5. Impact Propagation ──► BFS traversal            │
│  6. Compliance Mapping ──► action items + SOPs      │
│  6e. AI Insights ──► narrative grounded on the      │
│     numbers computed in step 0                      │
│  7. Audit + Metrics ──► audit_log.json              │
└─────────────────────────────────────────────────────┘
     │
     ▼
FastAPI Backend (port 8000) + Streamlit Dashboard (port 8501)
```

**Why step 0 exists.** The pipeline used to be LLM-only, so an unreachable provider
or a spent free-tier quota meant zero obligations and an HTTP 502. The local model
now carries the run on its own; the LLM improves the output when it is available
and is never required for it. `EXTRACTION_MODE=ml` makes this explicit — the whole
pipeline runs with no API key and no network.

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
│       │   ├── chat.py                # RAG chat over a processed circular
│       │   ├── intelligence.py        # local model: analyse / recognise / explain
│       │   └── health.py              # LLM preflight + API key status
│       ├── ml/                        # ← the local model (no network)
│       │   ├── corpus.py              # synthetic SEBI corpus + ground-truth labels
│       │   ├── pdf_render.py          # renders the corpus to SEBI-format PDFs
│       │   ├── train.py               # fits and persists the estimator bundle
│       │   ├── model.py               # inference + n-gram explainability
│       │   ├── features.py            # deontic modality + structural features
│       │   ├── extractor.py           # sentences → Obligation objects
│       │   ├── severity.py            # rule-first severity assessment
│       │   ├── insights.py            # deterministic pre-LLM document analysis
│       │   └── textutil.py            # block/sentence segmentation
│       ├── graph/obligation_graph.py  # NetworkX graph wrapper
│       ├── retrieval/faiss_search.py  # semantic similarity search
│       ├── anthropic_adapter.py       # OpenRouter ↔ Anthropic + key failover
│       ├── config.py                  # env-based configuration
│       └── main.py                    # FastAPI app + router registration
├── frontend/
│   ├── dashboard.py                   # Streamlit UI
│   └── intel_views.py                 # Document Intelligence + Chat pages
├── scripts/
│   ├── generate_corpus.py             # build the synthetic corpus PDFs
│   ├── train_model.py                 # train the local model
│   ├── evaluate_model.py              # precision/recall on held-out documents
│   ├── demo_scenario.py               # the end-to-end regulatory scenario
│   └── fetch_sebi_corpus.py           # download the real SEBI master circulars
├── data/                              # gitignored — all of it regenerable
│   ├── models/                        # trained bundle + model card
│   ├── corpus/                        # synthetic circulars + ground_truth.json
│   ├── sebi_corpus/                   # real SEBI master circulars
│   ├── obligation_graph.pkl           # persisted NetworkX graph
│   └── audit_log.json                 # timestamped audit trail
├── circular.pdf                       # SEBI Master Circular (Surveillance)
├── RUN.md                             # setup and run commands
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

### 2. Build the corpus and train the local model

Required — the offline extraction path needs it. Takes about 40 seconds.

```bash
venv/bin/python scripts/generate_corpus.py     # synthetic SEBI corpus → data/corpus/
venv/bin/python scripts/train_model.py         # trains → data/models/
venv/bin/python scripts/fetch_sebi_corpus.py   # real SEBI master circulars (optional)
venv/bin/python scripts/evaluate_model.py      # verify: P/R on held-out documents
```

> Use `venv/bin/python`, never bare `python`. The model is version-locked to the
> scikit-learn in the venv; loading it with a different one fails with an obscure
> `AttributeError` from inside sklearn.

### 3. Configure the API key (optional)

Everything works without one — the LLM only enriches the local model's output.

```bash
cp .env.example .env
# OPENROUTER_API_KEY=sk-or-v1-...
# OPENROUTER_API_KEY_BACKUP=...       # switched to automatically on a 429
# OPENROUTER_MODEL=openai/gpt-oss-20b:free
# OPENROUTER_MODEL=anthropic/claude-3.5-sonnet   # best results, needs credit
```

Get a free key at [openrouter.ai](https://openrouter.ai). The free tier allows
**50 requests/day per account** — extra keys on the same account share that limit.

To run with no LLM at all, set `EXTRACTION_MODE=ml`.

### 4. Start the backend

Run from the project root — paths resolve relative to the working directory.

```bash
PYTHONPATH=backend venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Start the dashboard

```bash
venv/bin/streamlit run frontend/dashboard.py --server.port 8501
```

### 6. Open in browser

| URL | Purpose |
|-----|---------|
| `http://localhost:8501` | Main dashboard |
| `http://localhost:8000/docs` | Swagger API docs |
| `http://localhost:8000/api/v1/health/llm` | LLM reachability + key status |

### 7. See the regulatory scenario

```bash
venv/bin/python scripts/demo_scenario.py       # 6 seconds, no API key needed
```

A stockbroker complies with the surveillance circular, SEBI amends it, and the
pipeline reports what changed (`deadline: 'within 30 days' → 'within 15 days'`),
who is affected downstream, and the resulting tasks.

---

## Running it on a circular

Drop a PDF on the **Document Intelligence** page for a local-only analysis (no
API quota spent), or on **Upload Circular** for the full pipeline. Or use the API:

```bash
curl -X POST http://localhost:8000/api/v1/circulars/upload-file \
  -F "file=@data/sebi_corpus/master-circular-for-stock-brokers_94623.pdf" \
  -F "circular_id=SEBI_MC_STOCKBROKERS_2025" \
  -F "title=Master Circular for Stock Brokers" \
  -F "intermediary_types=stockbroker"
```

Files worth trying:

| Path | What it demonstrates |
|---|---|
| `data/sebi_corpus/*.pdf` | the real SEBI master circulars |
| `data/corpus/holdout/*.pdf` | circulars the model has never seen |
| `data/corpus/negative/*.pdf` | non-circulars — should be rejected at 2–3% |
| `circular.pdf` | the 38-page surveillance master circular |

Demo the holdout and real files, not `data/corpus/*.pdf` — those are the model's
own training data.

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
| POST | `/api/v1/intel/analyze-file` | **Local model** — full analysis, no LLM |
| POST | `/api/v1/intel/recognize` | Is this a SEBI circular? Which family? |
| POST | `/api/v1/intel/explain` | Why the model classified a sentence that way |
| GET | `/api/v1/intel/model` | Model card: corpus, held-out scores |
| POST | `/api/v1/chat/ask` | Ask a question about a processed circular |
| GET | `/api/v1/chat/circulars` | Circulars available to chat with |
| GET | `/api/v1/copilot/pre-ai` | Deterministic analysis of the last run |
| GET | `/api/v1/copilot/ai-insights` | LLM insight layer for the last run |
| GET | `/api/v1/health/llm` | Provider reachability + API key status |

Full interactive docs: `http://localhost:8000/docs`

---

## What the local model does on real SEBI text

| Document | Pages | Recognition | Obligations | Time |
|---|---|---|---|---|
| Master Circular for Stock Brokers | 399 | circular ✅, topic outside trained families | 1,391 from 5,151 sentences | 7s |
| Master Circular for Investment Advisers | 99 | circular ✅, topic outside trained families | 238 | 1s |
| Master Circular on Surveillance (`circular.pdf`) | 38 | circular ✅ | 80 | <1s |
| Employment contract / press release / manual | 1 | **rejected** at 2–3% | — | <1s |

Every obligation carries its confidence, the n-grams that drove the decision, and
the rule that set its severity — inspect any of them via `POST /api/v1/intel/explain`.

The "topic outside trained families" verdict is deliberate: the model was trained
on five circular families and says so when a document is not one of them, rather
than asserting a label it cannot support.

---

## Problem Statement compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Specifies intermediary category | ✅ | **Stockbroker** primary, 5 more supported |
| Specifies regulatory corpus | ✅ | SEBI Master Circular for Stock Brokers (399 pp) + Investment Advisers (99 pp), fetched live |
| Concrete regulatory scenario | ✅ | `scripts/demo_scenario.py` — amendment vs circular in force, end to end in 6s |
| **Challenge 1** — dynamic regulatory translation | ✅ | Diff Agent classifies NEW / MODIFIED / SUPERSEDED and names the changed field (`deadline: 'within 30 days' → 'within 15 days'`) |
| Regulatory text → machine-actionable rules | ✅ | Typed `Obligation` schema + NetworkX graph + REST API |
| Maps to operational processes | ✅ | Action items per intermediary and per role, with generated SOP steps |
| **Challenge 2** — ongoing compliance management | ✅ | Evidence checklists, red/yellow/green gap status, risk-scored urgency queue |
| Evidence mapping | ✅ | `/api/v1/evidence/*` — per-obligation checklist and gap detection |
| Audit trail | ✅ | Every pipeline step timestamped in `data/audit_log.json` |
| Reduces issuance→action gap | ✅ | `scheduler/sebi_fetcher.py` scrapes SEBI's listing pages and auto-ingests new circulars |
| Measurable performance | ✅ | `scripts/evaluate_model.py` — P/R against ground truth, held-out documents |
| Accuracy | ✅ | precision 1.00 / recall 0.93 on unseen circulars; non-circulars rejected at 2–3% |
| Auditability of the AI itself | ✅ | Every obligation carries its confidence, the n-grams that drove the decision, and the rule that set its severity |
| Resilience | ✅ | Runs end to end with no LLM and no API key (`EXTRACTION_MODE=ml`) |

### Known limitations (stated deliberately)

- The severity classifier scores 0.52 on held-out templates, so severity is decided
  **rule-first** (prohibition, hard deadline, penalty language) with the model only
  breaking ties. Each obligation reports which decided it.
- The synthetic training corpus is template-generated, so the sentence-level F1 of
  1.00 in the model card is an upper bound. The held-out-document numbers above are
  the honest measure.
- On a 399-page master circular the local model extracts 1,391 candidate obligations;
  that is a review queue, not a final answer — the confidence score and the rejected-
  borderline list exist so an analyst can triage it.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| **Local model** | scikit-learn — TF-IDF (word 1-3 + char_wb 3-5) → logistic regression |
| **Corpus generation** | reportlab (renders labelled SEBI-format circulars to PDF) |
| LLM (enrichment only) | Claude / any OpenRouter model, with key failover |
| Backend | FastAPI + Uvicorn |
| Dashboard | Streamlit + Plotly |
| Graph | NetworkX (directed graph, BFS traversal) |
| Semantic search | FAISS + TF-IDF cosine |
| PDF parsing | pdfplumber |
| Data models | Pydantic v2 |
| Persistence | joblib (model) + pickle/JSON (graph, audit) |

---

## Notes

- The `data/` folder is gitignored and entirely regenerable — `generate_corpus.py`
  and `train_model.py` rebuild the corpus and model; `fetch_sebi_corpus.py` re-downloads
  the SEBI circulars
- `.env` is gitignored — never commit your API key
- Run everything with `venv/bin/python`, from the project root. The model is
  version-locked to the venv's scikit-learn, and data paths resolve relative to the
  working directory
- `mistralai/mistral-7b-instruct:free` was retired by OpenRouter (404). Working free
  models as of Aug 2026: `openai/gpt-oss-20b:free`, `google/gemma-4-31b-it:free`
- `anthropic/claude-3.5-sonnet` gives the best extraction quality (needs credit)
- The free tier is 50 requests/day **per account** — one 400-page circular can spend
  it. Set `OPENROUTER_API_KEY_BACKUP` to a key from a *different* account, or run
  `EXTRACTION_MODE=ml`
