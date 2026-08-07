# Deploying RegGraph

The container runs the API and the dashboard together and trains the local model
at build time, so a deployed instance behaves exactly like a local one — including
when no LLM API key is configured.

---

## Hugging Face Spaces (recommended)

**Why:** 16 GB RAM on the free CPU tier. Every other free tier is 512 MB, and the
backend peaks around 390 MB analysing a 38-page circular and higher on a 399-page
master circular — a 512 MB instance will run out of memory on your main demo.

### 1. Push to GitHub first

```bash
git checkout main
git merge feat/local-model-offline-pipeline
git push origin main
```

### 2. Create the Space

1. Go to https://huggingface.co/new-space
2. **Owner**: your account · **Space name**: e.g. `reggraph`
3. **License**: MIT
4. **SDK**: select **Docker** → **Blank**
5. **Hardware**: CPU basic (free)
6. **Visibility**: Public (or Private — both work)
7. Create Space

### 3. Push the code to the Space

The Space is its own git repository. From your project directory:

```bash
git remote add space https://huggingface.co/spaces/<your-username>/reggraph
git push space main
```

If it asks for a password, use a **write** access token from
https://huggingface.co/settings/tokens (not your account password).

The Space builds automatically. First build takes 8–15 minutes — it installs
scikit-learn, generates the corpus and trains the model. Watch the **Logs** tab.

You should see, near the end of the build:

```
model self-check OK, version 1.0.0
```

and then at runtime:

```
── RegGraph starting ──
  dashboard : 0.0.0.0:7860
  api       : 127.0.0.1:8000  (internal)
  api ready after Ns
```

### 4. Add an API key (optional)

The Space ships with `EXTRACTION_MODE=ml` — fully offline, no key needed, and
everything except the AI narrative layer and paraphrased chat answers works.

To enable the LLM layer: **Settings → Variables and secrets**

| Type | Name | Value |
|---|---|---|
| Secret | `OPENROUTER_API_KEY` | `sk-or-v1-…` |
| Secret | `OPENROUTER_API_KEY_BACKUP` | a key from a *different* account (optional) |
| Variable | `EXTRACTION_MODE` | `hybrid` |
| Variable | `ENABLE_AI_INSIGHTS` | `true` |
| Variable | `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` |

Never commit keys — the Space stores secrets as environment variables.

> The OpenRouter free tier is **50 requests/day per account**. A second key on the
> same account shares that limit and will not help.

---

## Other hosts

The same image works anywhere Docker runs. Two things matter:

**Memory: provision ≥ 1 GB.** Measured footprint:

| Stage | RSS |
|---|---|
| API + orchestrator | 106 MB |
| + local model loaded | 277 MB |
| + analysing a 38-page circular | 387 MB |

Streamlit adds ~350 MB. A 512 MB instance will be killed mid-upload.

**Port:** the dashboard binds `$PORT` (default 7860). Render and Railway inject
`PORT` automatically, so it works unchanged.

### Render

- New → Web Service → connect the repo → Runtime: **Docker**
- Instance type: **Standard** or larger (free/starter at 512 MB will OOM)
- No build or start command needed — the Dockerfile handles both

### Railway

- New Project → Deploy from GitHub → it detects the Dockerfile
- Settings → set memory limit ≥ 1 GB

### Deploying without Docker

If the host runs Python directly rather than the Dockerfile, the model is **not**
built for you and the deploy will silently fall back to LLM-only. Set the build
command explicitly:

```bash
pip install -r requirements.txt && \
python scripts/generate_corpus.py && \
python scripts/train_model.py
```

and run two processes (`uvicorn app.main:app` and `streamlit run frontend/dashboard.py`),
with `API_BASE_URL` on the dashboard pointing at the backend.

---

## Verifying a deployment

```bash
BASE=https://<your-space>.hf.space          # or your host's URL

curl $BASE/health                            # {"status":"ok"}
```

In the dashboard, go to **Document Intelligence → Model card & corpus**. If it
shows the model version and the held-out scores, the local model deployed
correctly. If it says "No trained model found", the build step did not run —
check the build logs.

Then upload `data/corpus/holdout/holdout_amendment__surveillance__204.pdf` on the
Document Intelligence page. It should recognise it as a surveillance circular and
extract 15 obligations, with no API key configured.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Space build fails on `COPY` | `.dockerignore` excluding a needed path | check `frontend/`, `scripts/`, `backend/` are not ignored |
| Permission denied at runtime | writing outside the UID-1000 user's home | all app paths live under `/home/user/app`; don't hardcode `/app` |
| "No trained model found" | build skipped the training step | check build logs for `model self-check OK` |
| Dashboard loads, every page errors | API not reachable | `API_BASE_URL` must point at the internal API port |
| Killed / restarts under load | out of memory | provision ≥ 1 GB |
| Blank page inside the Space iframe | Streamlit CORS/XSRF | already disabled in `start.sh`; confirm `app_port: 7860` matches |
| 502 on upload, zero obligations | LLM-only mode with no key | set `EXTRACTION_MODE=ml` (or add a key) |
