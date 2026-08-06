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

# Copy backend source
COPY backend/ ./backend/

# Data dir — override with a mounted volume in production
# e.g. Render: mount a persistent disk at /data and set DATA_DIR=/data
RUN mkdir -p /app/data

ENV PYTHONPATH=/app/backend
ENV DATA_DIR=/app/data
ENV FAISS_INDEX_PATH=/app/data/faiss_index
ENV GRAPH_DB_PATH=/app/data/obligation_graph.pkl
ENV LOG_LEVEL=INFO
ENV PORT=8000

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
