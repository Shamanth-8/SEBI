FROM python:3.11-slim

WORKDIR /app

# System deps for pdfplumber (pdfminer uses native libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source and the corpus/training scripts
COPY backend/ ./backend/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app/backend

# Build the synthetic corpus and train the local model INTO THE IMAGE.
# Without this the container starts with no model, the offline extraction path is
# dead, and the pipeline silently degrades to LLM-only — which is exactly the
# failure mode this architecture exists to avoid. Training takes ~40s and the
# artifacts are ~1.2 MB, so it belongs at build time, not first request.
RUN python scripts/generate_corpus.py \
    && python scripts/train_model.py \
    && python -c "import sys; sys.path.insert(0,'backend'); \
from app.ml.model import RegGraphModel; \
m=RegGraphModel.load(); \
print('model self-check OK, version', m.version)"

# Runtime data dir — override with a mounted volume in production
# e.g. Render: mount a persistent disk at /data and set DATA_DIR=/data
RUN mkdir -p /app/data

ENV DATA_DIR=/app/data
ENV FAISS_INDEX_PATH=/app/data/faiss_index
ENV GRAPH_DB_PATH=/app/data/obligation_graph.pkl
# Model artifacts live in the image, not on the mounted volume — a volume mount
# at /app/data would otherwise hide them.
ENV MODEL_DIR=/app/models
ENV CORPUS_DIR=/app/corpus
RUN mkdir -p /app/models && cp -r /app/data/models/. /app/models/ \
    && cp -r /app/data/corpus /app/corpus \
    && rm -rf /app/data/models
ENV LOG_LEVEL=INFO
ENV PORT=8000

# Local model first, LLM as enrichment. The container therefore serves useful
# results even with no API key configured.
ENV EXTRACTION_MODE=hybrid

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://localhost:8000/health', timeout=4).status_code==200 else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
