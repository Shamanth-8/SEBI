"""
Conversational agent over an uploaded circular.

Retrieval-augmented: the question is matched against passages of the actual
document (and the obligations extracted from it), and only those passages are
sent to the LLM. Answers therefore cite clause text rather than the model's
recollection of SEBI rules.

If the LLM is unreachable or out of quota the agent degrades to an extractive
answer built from the same retrieved passages — the chat stays usable offline,
it just stops paraphrasing.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import get_settings
from app.ml.textutil import clean_text, segment_blocks

logger = logging.getLogger(__name__)

STORE_DIR = Path("data/chat_index")
MAX_HISTORY_TURNS = 6


@dataclass
class Passage:
    passage_id: str
    text: str
    section: str = "General"
    kind: str = "document"          # "document" | "obligation"
    obligation_id: Optional[str] = None
    score: float = 0.0


@dataclass
class IndexedCircular:
    circular_id: str
    title: str
    text: str
    passages: List[Passage] = field(default_factory=list)
    indexed_at: float = 0.0
    metrics: Dict = field(default_factory=dict)


# ── Chunking ─────────────────────────────────────────────────────────────────

def _build_passages(text: str, target_chars: int = 900) -> List[Passage]:
    """
    Group document blocks into passages that stay inside clause boundaries.

    Splitting on a fixed character count would cut clauses in half and produce
    citations that don't correspond to anything a compliance officer can look up.
    """
    passages: List[Passage] = []
    section = "General"
    buf: List[str] = []
    size = 0

    def flush():
        nonlocal buf, size
        if buf:
            passages.append(Passage(
                passage_id=f"p{len(passages):03d}",
                text=" ".join(buf).strip(),
                section=section,
            ))
            buf, size = [], 0

    for kind, block in segment_blocks(text):
        if kind == "heading":
            flush()
            section = block.strip()
            continue
        if size + len(block) > target_chars and buf:
            flush()
        buf.append(block)
        size += len(block)
    flush()
    return [p for p in passages if len(p.text) > 40]


# ── The agent ────────────────────────────────────────────────────────────────

class CircularChatAgent:
    """One instance per process; circulars are cached on disk between restarts."""

    def __init__(self, store_dir: Path = STORE_DIR):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, IndexedCircular] = {}
        self._settings = get_settings()

    # ── Indexing ──────────────────────────────────────────────────────────

    def index_circular(self, circular_id: str, title: str, text: str,
                       obligations: Optional[List] = None,
                       metrics: Optional[Dict] = None) -> IndexedCircular:
        """Store a circular's text + its obligations so both are retrievable."""
        passages = _build_passages(clean_text(text))

        for o in (obligations or []):
            passages.append(Passage(
                passage_id=f"o{len(passages):03d}",
                text=(f"Obligation: {o.title}. {o.description} "
                      f"Responsible: {o.responsible_party}. "
                      f"Deadline: {o.deadline or 'not specified'}. "
                      f"Severity: {o.severity}. "
                      f"Evidence required: {'; '.join(o.evidence_requirements)}."),
                section=o.clause_reference[:80] if o.clause_reference else "Obligation",
                kind="obligation",
                obligation_id=o.obligation_id,
            ))

        indexed = IndexedCircular(
            circular_id=circular_id, title=title, text=text,
            passages=passages, indexed_at=time.time(),
            metrics=metrics or {},
        )
        self._cache[circular_id] = indexed
        self._persist(indexed)
        logger.info(f"Chat index built for {circular_id}: {len(passages)} passages")
        return indexed

    def _persist(self, indexed: IndexedCircular) -> None:
        payload = {
            "circular_id": indexed.circular_id,
            "title": indexed.title,
            "text": indexed.text,
            "indexed_at": indexed.indexed_at,
            "metrics": indexed.metrics,
            "passages": [
                {"passage_id": p.passage_id, "text": p.text, "section": p.section,
                 "kind": p.kind, "obligation_id": p.obligation_id}
                for p in indexed.passages
            ],
        }
        path = self.store_dir / f"{self._safe(indexed.circular_id)}.json"
        path.write_text(json.dumps(payload))

    @staticmethod
    def _safe(circular_id: str) -> str:
        return re.sub(r'[^A-Za-z0-9_.-]', '_', circular_id)[:120]

    def get(self, circular_id: str) -> Optional[IndexedCircular]:
        if circular_id in self._cache:
            return self._cache[circular_id]
        path = self.store_dir / f"{self._safe(circular_id)}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except Exception as exc:
            logger.warning(f"Could not read chat index {path}: {exc}")
            return None
        indexed = IndexedCircular(
            circular_id=data["circular_id"], title=data.get("title", ""),
            text=data.get("text", ""), indexed_at=data.get("indexed_at", 0.0),
            metrics=data.get("metrics", {}),
            passages=[Passage(**p) for p in data.get("passages", [])],
        )
        self._cache[indexed.circular_id] = indexed
        return indexed

    def list_indexed(self) -> List[Dict]:
        out = []
        for path in sorted(self.store_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except Exception:
                continue
            out.append({
                "circular_id": data.get("circular_id"),
                "title": data.get("title", ""),
                "passages": len(data.get("passages", [])),
                "indexed_at": data.get("indexed_at", 0.0),
                "characters": len(data.get("text", "")),
            })
        return sorted(out, key=lambda d: -d["indexed_at"])

    # ── Retrieval ─────────────────────────────────────────────────────────

    def retrieve(self, indexed: IndexedCircular, question: str, k: int = 5) -> List[Passage]:
        """TF-IDF cosine retrieval, with a keyword-overlap fallback."""
        texts = [p.text for p in indexed.passages]
        if not texts:
            return []
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                  sublinear_tf=True)
            M = vec.fit_transform(texts)
            q = vec.transform([question])
            sims = cosine_similarity(q, M)[0]
        except Exception as exc:                       # sklearn missing or degenerate vocab
            logger.debug(f"TF-IDF retrieval unavailable ({exc}); using keyword overlap")
            qs = {w for w in re.findall(r"[a-z]{3,}", question.lower())}
            sims = [
                len(qs & set(re.findall(r"[a-z]{3,}", t.lower()))) / max(len(qs), 1)
                for t in texts
            ]

        ranked = sorted(zip(indexed.passages, sims), key=lambda kv: -kv[1])
        out = []
        for p, s in ranked[:k]:
            if s <= 0:
                continue
            hit = Passage(**{**p.__dict__})
            hit.score = round(float(s), 4)
            out.append(hit)
        return out

    # ── Answering ─────────────────────────────────────────────────────────

    def answer(self, question: str, circular_id: str,
               history: Optional[List[Dict]] = None, k: int = 5) -> Dict:
        """
        Answer a question about one indexed circular.

        Returns {answer, sources, mode, ...}. `mode` is "llm" or "extractive" so
        the UI can be honest about which one produced the text.
        """
        t0 = time.perf_counter()
        indexed = self.get(circular_id)
        if indexed is None:
            return {
                "answer": (f"No circular is indexed under id `{circular_id}`. "
                           "Upload and process it first, then ask again."),
                "sources": [], "mode": "error", "circular_id": circular_id,
            }

        passages = self.retrieve(indexed, question, k=k)
        if not passages:
            return {
                "answer": ("Nothing in this circular matches that question. Try naming a "
                           "specific term from the document (for example a section heading, "
                           "an obligation, or a deadline)."),
                "sources": [], "mode": "extractive", "circular_id": circular_id,
            }

        sources = [
            {"passage_id": p.passage_id, "section": p.section, "kind": p.kind,
             "obligation_id": p.obligation_id, "score": p.score,
             "excerpt": p.text[:400] + ("…" if len(p.text) > 400 else "")}
            for p in passages
        ]

        llm_answer, error = self._llm_answer(question, indexed, passages, history or [])
        if llm_answer:
            return {
                "answer": llm_answer, "sources": sources, "mode": "llm",
                "circular_id": circular_id, "model": self._settings.LLM_MODEL,
                "latency_seconds": round(time.perf_counter() - t0, 2),
            }

        return {
            "answer": self._extractive_answer(question, passages),
            "sources": sources, "mode": "extractive", "circular_id": circular_id,
            "llm_error": error,
            "latency_seconds": round(time.perf_counter() - t0, 2),
        }

    def _context_block(self, indexed: IndexedCircular, passages: List[Passage]) -> str:
        lines = []
        for p in passages:
            tag = f"[{p.passage_id} · {p.section[:60]}]"
            lines.append(f"{tag}\n{p.text}")
        return "\n\n".join(lines)

    def _llm_answer(self, question: str, indexed: IndexedCircular,
                    passages: List[Passage],
                    history: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
        try:
            from app.anthropic_adapter import create_anthropic_compatible_client
            from app.llm_errors import call_with_retry
        except Exception as exc:                                   # pragma: no cover
            return None, f"LLM client unavailable: {exc}"

        metrics = indexed.metrics or {}
        metrics_line = ""
        if metrics:
            metrics_line = (
                "\nPre-computed analysis of this circular (from the local model — treat as "
                "ground truth, do not contradict it):\n"
                + json.dumps(metrics, indent=2)[:1200]
            )

        convo = ""
        for turn in history[-MAX_HISTORY_TURNS:]:
            role = "User" if turn.get("role") == "user" else "Assistant"
            convo += f"{role}: {turn.get('content', '')[:600]}\n"
        # Built outside the f-string: a backslash inside an f-string expression is
        # a syntax error before Python 3.12.
        convo_block = ("Conversation so far:\n" + convo) if convo else ""

        prompt = f"""You are a SEBI compliance analyst answering questions about one specific circular.

Circular: {indexed.title or indexed.circular_id} (id: {indexed.circular_id})
{metrics_line}

Relevant passages retrieved from the circular:
---
{self._context_block(indexed, passages)}
---
{convo_block}
Question: {question}

Rules for your answer:
- Answer ONLY from the passages above. If they do not contain the answer, say so plainly and
  suggest what to search for instead. Never invent a clause, deadline or penalty.
- Cite the passage tags you used, like [p012], at the end of the sentence they support.
- Be specific about deadlines, responsible parties and evidence when the passages state them.
- Keep it under 200 words unless the question needs a list. Use short bullets for lists.
- Write for a compliance officer: direct, no preamble, no restating the question."""

        try:
            client = create_anthropic_compatible_client(self._settings.LLM_PROVIDER)
            message = call_with_retry(
                lambda: client.messages.create(
                    model=self._settings.LLM_MODEL,
                    max_tokens=900,
                    messages=[{"role": "user", "content": prompt}],
                ),
                max_retries=self._settings.LLM_MAX_RETRIES,
                label="chat",
            )
            text = (message.content[0].text or "").strip()
            return (text, None) if text else (None, "Model returned an empty response")
        except Exception as exc:
            logger.warning(f"Chat LLM call failed: {exc}")
            return None, str(exc)

    @staticmethod
    def _extractive_answer(question: str, passages: List[Passage]) -> str:
        """
        No-LLM fallback: return the most relevant clause text verbatim.

        Deliberately quotes rather than paraphrases — without a language model
        there is no safe way to summarise regulatory text.
        """
        head = ("The language model is unavailable, so here are the passages from the "
                "circular that best match your question, quoted verbatim:\n")
        body = []
        for p in passages[:3]:
            excerpt = p.text if len(p.text) <= 600 else p.text[:600] + "…"
            body.append(f"\n**{p.section[:70]}** · relevance {p.score:.2f}\n> {excerpt}")
        return head + "\n".join(body)


# Module-level singleton shared by the API routers
_agent: Optional[CircularChatAgent] = None


def get_chat_agent() -> CircularChatAgent:
    global _agent
    if _agent is None:
        _agent = CircularChatAgent()
    return _agent
