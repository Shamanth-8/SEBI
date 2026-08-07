# RegGraph — API + dashboard in one container.
#
# Targets Hugging Face Spaces (sdk: docker), which runs the container as UID 1000
# and exposes a single port. Works unchanged on Render/Railway/Fly/any Docker host;
# override PORT to move the dashboard.
FROM python:3.11-slim

# System deps for pdfplumber (pdfminer uses native libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces runs as UID 1000. Creating that user here — and owning every path the
# app writes — avoids the permission errors that are the usual cause of a Space
# building fine and then failing at runtime.
# The app directory must be created AND chowned before switching user: WORKDIR
# creates missing directories as the *current* user (root at this point), so
# doing it afterwards leaves a root-owned tree that UID 1000 cannot write —
# the build then fails on the first mkdir with "Permission denied".
RUN useradd -m -u 1000 user \
 && mkdir -p /home/user/app \
 && chown -R user:user /home/user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# Dependencies first so the layer caches across code changes
COPY --chown=user requirements.txt .
USER user
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user backend/  ./backend/
COPY --chown=user frontend/ ./frontend/
COPY --chown=user scripts/  ./scripts/
COPY --chown=user start.sh  ./start.sh

ENV PYTHONPATH=$HOME/app/backend

# Build the corpus and train the local model INTO THE IMAGE. Without this the
# container starts with no model, the offline extraction path is dead, and the
# pipeline silently degrades to LLM-only — the failure this design exists to
# prevent. ~40s at build time; the alternative is a broken first request.
RUN python scripts/generate_corpus.py \
 && python scripts/train_model.py \
 && python -c "import sys; sys.path.insert(0,'backend'); \
from app.ml.model import RegGraphModel; \
m = RegGraphModel.load(); \
print('model self-check OK, version', m.version)"

# Model and corpus live outside ./data so a mounted volume at ./data cannot hide
# them (that mistake makes the offline path vanish with no error message).
ENV MODEL_DIR=$HOME/app/models \
    CORPUS_DIR=$HOME/app/corpus
RUN mkdir -p "$MODEL_DIR" "$CORPUS_DIR" \
 && cp -r data/models/. "$MODEL_DIR"/ \
 && cp -r data/corpus/. "$CORPUS_DIR"/ \
 && rm -rf data/models \
 && mkdir -p data

ENV DATA_DIR=$HOME/app/data \
    FAISS_INDEX_PATH=$HOME/app/data/faiss_index \
    GRAPH_DB_PATH=$HOME/app/data/obligation_graph.pkl \
    LOG_LEVEL=INFO

# Local model first, LLM as enrichment: the Space serves useful results even with
# no API key set. Override to "hybrid" once a key is configured as a Space secret.
ENV EXTRACTION_MODE=ml \
    ENABLE_AI_INSIGHTS=false

# 7860 is the Hugging Face Spaces default; app_port in README.md must match.
ENV PORT=7860 \
    API_PORT=8000
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import sys,urllib.request; \
urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0)"

CMD ["bash", "start.sh"]
