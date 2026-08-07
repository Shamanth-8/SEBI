# Running RegGraph

## One-time setup

```bash
cd /run/media/shamath/C4CAC629CAC61796/code/sebi

# 1. Dependencies (adds scikit-learn, joblib, reportlab)
./venv/bin/pip install -r requirements.txt

# 2. Generate the synthetic SEBI corpus → data/corpus/
#    5 demo circular PDFs + 2 holdout PDFs + 4 non-circular PDFs + ground_truth.json
./venv/bin/python scripts/generate_corpus.py

# 3. Train the local model → data/models/reggraph_model.joblib + model_card.json
./venv/bin/python scripts/train_model.py

# 4. Download the real SEBI master circulars (stock brokers + investment advisers)
./venv/bin/python scripts/fetch_sebi_corpus.py

# 5. Verify — precision/recall against ground truth, on held-out documents
./venv/bin/python scripts/evaluate_model.py
```

Steps 2 and 3 take about 40 seconds together. Re-run step 3 whenever you change
the corpus or the feature set.

## Running the app

Two terminals.

**Terminal 1 — backend (port 8000):**
```bash
cd /run/media/shamath/C4CAC629CAC61796/code/sebi
PYTHONPATH=backend ./venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — dashboard (port 8501):**
```bash
cd /run/media/shamath/C4CAC629CAC61796/code/sebi
./venv/bin/streamlit run frontend/dashboard.py
```

Then open http://localhost:8501 — API docs are at http://localhost:8000/docs.

## Where things are in the UI

| Page | What it does |
|---|---|
| **Document Intelligence** | Upload any PDF → local model recognises it and extracts obligations with charts. No LLM, no API quota. Second tab shows the model card and training corpus. |
| **Upload Circular** | Full pipeline. Results come back in two tabs: *Local analysis (no LLM)* and *AI insights (LLM layer)*. |
| **Ask the Circular** | Chat about any processed circular, with the source passages shown next to each answer. |

## The demo to show a judge

```bash
./venv/bin/python scripts/demo_scenario.py
```

Runs the concrete regulatory scenario end to end in about 6 seconds, with no API
key: a stockbroker is compliant with the surveillance circular, SEBI amends it,
and the pipeline reports what changed (`deadline: 'within 30 days' → 'within 15
days'`), who is affected downstream, and the tasks that result.

Add `--with-llm` to also run the LLM enrichment and insight layer.

## Try these files

```
data/sebi_corpus/*.pdf             REAL SEBI master circulars (399pp brokers, 99pp advisers)
data/corpus/holdout/*.pdf          2 synthetic circulars the model has never seen
data/corpus/negative/*.pdf         non-circulars — it should reject these
data/corpus/*.pdf                  the 5 circulars it was trained on (don't demo these)
circular.pdf                       the 38-page SEBI surveillance master circular
```

Demo the **real master circulars** and the **holdout** files. Showing a model's
score on its own training data is the first thing a reviewer will discount.

## Running without an API key

```bash
EXTRACTION_MODE=ml ENABLE_AI_INSIGHTS=false \
  PYTHONPATH=backend ./venv/bin/python -m uvicorn app.main:app --port 8000
```

Everything still works except the AI insight layer and paraphrased chat answers
(chat falls back to quoting the matching passages verbatim).
