"""
Chat endpoints — ask questions about a processed circular.
"""
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.chat_agent import get_chat_agent

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    circular_id: str
    history: Optional[List[Dict]] = None
    top_k: int = 5


class IndexRequest(BaseModel):
    circular_id: str
    title: str = ""
    document_text: str


@router.post("/ask")
async def ask(request: ChatRequest):
    """
    Answer a question grounded in one circular.

    The response carries `mode`: "llm" when the language model answered,
    "extractive" when it was unreachable and the passages were quoted instead.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is empty")
    try:
        return get_chat_agent().answer(
            question=request.question,
            circular_id=request.circular_id,
            history=request.history or [],
            k=request.top_k,
        )
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index")
async def index(request: IndexRequest):
    """
    Index a circular for chat without running the full pipeline.

    Useful for asking questions about a document you don't want to add to the
    obligation graph yet.
    """
    if not request.document_text.strip():
        raise HTTPException(status_code=400, detail="document_text is empty")
    indexed = get_chat_agent().index_circular(
        circular_id=request.circular_id,
        title=request.title,
        text=request.document_text,
    )
    return {
        "circular_id": indexed.circular_id,
        "title": indexed.title,
        "passages": len(indexed.passages),
        "characters": len(indexed.text),
    }


@router.get("/circulars")
async def list_chat_circulars():
    """Circulars available to chat with."""
    items = get_chat_agent().list_indexed()
    return {"count": len(items), "circulars": items}


@router.get("/suggestions/{circular_id}")
async def suggestions(circular_id: str):
    """
    Starter questions for the chat UI.

    Built from what the circular actually contains, so they always have an answer
    — generic suggestions that return "not in this document" are worse than none.
    """
    agent = get_chat_agent()
    indexed = agent.get(circular_id)
    if indexed is None:
        raise HTTPException(status_code=404, detail=f"Circular {circular_id} is not indexed")

    metrics = (indexed.metrics or {}).get("summary_metrics", {})
    out = [
        "Summarise this circular in five bullet points.",
        "What are the highest-severity obligations and who owns them?",
    ]
    if metrics.get("with_deadline"):
        out.append("List every obligation with a deadline, earliest first.")
    if metrics.get("recurring_obligations"):
        out.append("Which obligations are recurring, and at what frequency?")
    if metrics.get("prohibitions"):
        out.append("What does this circular prohibit outright?")
    out.append("What evidence do we need to collect to demonstrate compliance?")

    sections = list(dict.fromkeys(
        p.section for p in indexed.passages if p.kind == "document" and p.section != "General"
    ))[:3]
    for s in sections:
        out.append(f"What does the section '{s[:50]}' require?")
    return {"circular_id": circular_id, "suggestions": out[:8]}
