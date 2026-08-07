"""
Document intelligence endpoints — the local model, exposed directly.

These run without touching the LLM, so the dashboard can show a full analysis of
an uploaded PDF (recognition, obligations, charts) before the user commits to a
pipeline run that costs API quota.
"""
import io
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.ml import insights as ml_insights
from app.ml.model import ModelNotTrained, RegGraphModel

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    document_text: str
    circular_id: str = "PREVIEW"
    title: str = ""
    intermediary_types: Optional[List[str]] = None
    threshold: float = 0.55
    pages: int = 0


def _pdf_text(content: bytes, filename: str) -> str:
    """Extract the text layer, with the same error messages the upload path uses."""
    if filename.lower().endswith(".pdf"):
        import pdfplumber
        text = ""
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read PDF '{filename}': {e}")
        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail=f"No text layer in '{filename}' — this looks like a scanned image PDF. "
                       "Run OCR first, or paste the text.",
            )
        return text
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


@router.post("/analyze")
async def analyze_text(request: AnalyzeRequest):
    """Full local analysis of a circular supplied as text. No LLM involved."""
    try:
        return ml_insights.analyze(
            request.document_text,
            pages=request.pages,
            circular_id=request.circular_id,
            circular_title=request.title,
            intermediary_types=request.intermediary_types,
            threshold=request.threshold,
        )
    except ModelNotTrained as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Local analysis failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze-file")
async def analyze_file(
    file: UploadFile = File(...),
    circular_id: str = Form("PREVIEW"),
    title: str = Form(""),
    intermediary_types: Optional[str] = Form(None),
    threshold: float = Form(0.55),
):
    """Same as /analyze but takes the PDF directly."""
    content = await file.read()
    filename = file.filename or ""
    text = _pdf_text(content, filename)

    pages = 0
    if filename.lower().endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = len(pdf.pages)
        except Exception:
            pages = 0

    itypes = [t.strip() for t in intermediary_types.split(",")] if intermediary_types else None
    try:
        result = ml_insights.analyze(
            text, pages=pages, circular_id=circular_id, circular_title=title,
            intermediary_types=itypes, threshold=threshold,
        )
    except ModelNotTrained as e:
        raise HTTPException(status_code=503, detail=str(e))
    result["filename"] = filename
    result["document_text_length"] = len(text)
    return result


@router.post("/recognize")
async def recognize(request: AnalyzeRequest):
    """Just the document recogniser — fast enough for an as-you-type preview."""
    try:
        return RegGraphModel.get().recognize_document(request.document_text)
    except ModelNotTrained as e:
        raise HTTPException(status_code=503, detail=str(e))


class ExplainRequest(BaseModel):
    sentence: str
    head: str = "obligation_clf"
    top_k: int = 8


@router.post("/explain")
async def explain(request: ExplainRequest):
    """
    Why did the model decide that? Returns the signed contribution of each n-gram
    to the decision function — the actual arithmetic, not a narrative.
    """
    try:
        model = RegGraphModel.get()
        scored = model.classify_sentences([request.sentence])[0]
        return {
            "sentence": request.sentence,
            "prediction": scored,
            "contributions": model.explain(request.sentence, request.head, request.top_k),
        }
    except ModelNotTrained as e:
        raise HTTPException(status_code=503, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown model head '{request.head}'")


@router.get("/model")
async def model_info():
    """Model card: corpus composition, held-out scores, label distributions."""
    if not RegGraphModel.available():
        return {
            "trained": False,
            "message": "No trained model. Run: python scripts/train_model.py",
        }
    info = RegGraphModel.get().info()
    info["trained"] = True
    return info


@router.get("/corpus")
async def corpus_info():
    """The synthetic corpus the model was trained on, with links to the PDFs."""
    from pathlib import Path

    # CORPUS_DIR lets a container keep the corpus outside a mounted data volume.
    corpus_dir = Path(os.getenv("CORPUS_DIR", "data/corpus"))
    if not corpus_dir.exists():
        return {"generated": False,
                "message": "Run: python scripts/generate_corpus.py"}

    def listing(d: Path):
        if not d.exists():
            return []
        return sorted(
            ({"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1), "path": str(p)}
             for p in d.glob("*.pdf")),
            key=lambda x: x["name"],
        )

    return {
        "generated": True,
        "demo_circulars": listing(corpus_dir),
        "holdout_circulars": listing(corpus_dir / "holdout"),
        "negative_documents": listing(corpus_dir / "negative"),
    }
