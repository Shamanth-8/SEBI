"""
Obligation extraction agent using Claude LLM (via Anthropic or OpenRouter).
Parses regulatory circulars into obligation nodes.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from app.models.obligation import Obligation, CircularMetadata, ObligationStatus, EvidenceStatus
from app.config import get_settings
from app.anthropic_adapter import create_anthropic_compatible_client
from app.llm_errors import LLMError, LLMFatalError, call_with_retry

logger = logging.getLogger(__name__)


class ObligationExtractionAgent:
    """
    Agent that extracts obligations from regulatory circulars using Claude.
    Works with both Anthropic and OpenRouter providers.
    """
    
    def __init__(self):
        settings = get_settings()
        self.client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
        self.settings = settings
        self.model = self.settings.LLM_MODEL
        self.conversation_history = []
        # Per-run extraction failure tracking (see extract_obligations)
        self.chunks_failed = 0
        self.chunks_total = 0
        self.last_error: Optional[str] = None
        self._counter_lock = threading.Lock()
        logger.info(f"Initialized extraction agent with provider: {settings.LLM_PROVIDER}, model: {self.model}")
    
    def extract_obligations(
        self,
        circular_text: str,
        circular_id: str,
        circular_title: str,
        intermediary_types: Optional[List[str]] = None
    ) -> List[Obligation]:
        """
        Extract obligations from circular text.
        
        Args:
            circular_text: Full text of the regulatory circular
            circular_id: Identifier for the circular
            circular_title: Title of the circular
            intermediary_types: List of intermediary types affected
            
        Returns:
            List of extracted Obligation objects
        """
        if intermediary_types is None:
            intermediary_types = ["stockbroker", "rta", "investment_adviser"]

        self.conversation_history = []
        # Reset per-run failure tracking so callers can tell "found nothing" from
        # "every call failed".
        self.chunks_failed = 0
        self.chunks_total = 0
        self.last_error: Optional[str] = None

        # Step 1: Chunk the circular into logical sections
        logger.info(f"Extracting obligations from circular {circular_id}")

        chunks = self._chunk_circular(circular_text)
        self.chunks_total = len(chunks)
        logger.info(f"Circular split into {len(chunks)} chunks")

        # Step 2: Extract obligations from each chunk, a few at a time.
        # A fatal error (bad model / bad key) aborts the whole run immediately —
        # retrying it once per chunk would just waste the daily quota.
        def run_chunk(idx_chunk):
            i, chunk = idx_chunk
            chunk_text = chunk["text"] if isinstance(chunk, dict) else chunk
            section_hint = chunk.get("section_hint", "General") if isinstance(chunk, dict) else "General"
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            return self._extract_from_chunk(
                chunk_text, circular_id, circular_title, intermediary_types, section_hint
            )

        workers = max(1, min(self.settings.LLM_CONCURRENCY, len(chunks)))
        all_obligations: List[Obligation] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for obligations in pool.map(run_chunk, enumerate(chunks)):
                all_obligations.extend(obligations)

        if self.chunks_total and self.chunks_failed >= self.chunks_total:
            raise LLMError(
                f"All {self.chunks_total} extraction calls failed. Last error: {self.last_error}",
                kind="fatal",
            )

        # Renumber so ids stay unique regardless of chunk completion order.
        for n, obl in enumerate(all_obligations):
            obl.obligation_id = f"{circular_id}_obl_{n}"

        # Step 3: Identify relationships between obligations
        logger.info(f"Extracted {len(all_obligations)} obligations. Linking relationships...")
        all_obligations = self._link_obligation_relationships(all_obligations)

        logger.info(
            f"Successfully extracted {len(all_obligations)} obligations "
            f"({self.chunks_failed}/{self.chunks_total} chunks failed)"
        )
        return all_obligations
    
    def _chunk_circular(self, text: str, chunk_size: Optional[int] = None) -> List[dict]:
        """
        Split circular into logical chunks, preserving section/clause headings
        so clause_reference can point to the actual source paragraph.

        Returns list of dicts: {"text": str, "section_hint": str}
        """
        import re

        if chunk_size is None:
            chunk_size = self.settings.EXTRACTION_CHUNK_SIZE
        # Detect numbered headings like "2.", "2.1", "3.4.1", "A.", "PART I"
        heading_re = re.compile(
            r'(?m)^(?P<heading>'
            r'(?:\d+\.)+\d*\s+[A-Z][^\n]{3,80}'   # 2.1 HEADING TEXT
            r'|[A-Z][A-Z\s]{4,60}'                  # ALLCAPS HEADING
            r'|(?:PART|CHAPTER|SECTION)\s+\w+'       # PART / CHAPTER / SECTION
            r')'
        )

        lines = text.splitlines(keepends=True)
        chunks = []
        current_text = ""
        current_heading = "General"

        for line in lines:
            m = heading_re.match(line)
            if m and len(current_text.strip()) > 200:
                # Flush current chunk
                chunks.append({"text": current_text.strip(), "section_hint": current_heading})
                current_text = line
                current_heading = m.group("heading").strip()
            else:
                current_text += line
                if len(current_text) >= chunk_size:
                    chunks.append({"text": current_text.strip(), "section_hint": current_heading})
                    current_text = ""

        if current_text.strip():
            chunks.append({"text": current_text.strip(), "section_hint": current_heading})

        return chunks
    
    def _extract_from_chunk(
        self,
        chunk: str,
        circular_id: str,
        circular_title: str,
        intermediary_types: List[str],
        section_hint: str = "General"
    ) -> List[Obligation]:
        """Extract obligations from a single chunk using Claude."""
        
        extraction_prompt = f"""You are a regulatory compliance expert specializing in SEBI (Securities and Exchange Board of India) regulations.

Analyze the following excerpt from the regulatory circular "{circular_title}" (section: {section_hint}) and extract ALL distinct obligations, requirements, or compliance tasks.

For each obligation, identify:
1. clause_reference: The EXACT sentence or clause number from the text that defines this obligation (e.g. "Clause 4(b): All stockbrokers shall...")
2. Specific action required (verb + object)
3. Who is responsible (compliance officer, board, risk committee, etc.)
4. Deadline or frequency (if mentioned)
5. Type of deadline (fixed date, recurring, within X days, etc.)
6. Who must comply (intermediary types)
7. Any conditions or exceptions
8. Evidence needed to demonstrate compliance

CIRCULAR EXCERPT (Section: {section_hint}):
---
{chunk}
---

Return a JSON array of obligations. Each obligation MUST have this structure:
{{
  "clause_reference": "Exact quoted sentence or clause number from the text above that states this obligation",
  "title": "Brief title of obligation",
  "description": "Detailed description of what must be done",
  "responsible_party": "Who is responsible",
  "required_action": "Specific action",
  "deadline": "Deadline if mentioned or null",
  "deadline_type": "fixed/recurring/relative/not_specified",
  "intermediary_types": {json.dumps(intermediary_types)},
  "conditions": {{}},
  "evidence_requirements": ["evidence type 1", "evidence type 2"],
  "keywords": ["keyword1", "keyword2"],
  "severity": "high/medium/low"
}}

If no obligations are found, return an empty array [].
Return ONLY valid JSON, no markdown or explanation."""

        try:
            # Call the LLM. Transient failures (429/5xx) are retried with backoff;
            # fatal ones (bad model id, bad key) raise straight away.
            message = call_with_retry(
                lambda: self.client.messages.create(
                    model=self.model,
                    # A 6000-char chunk routinely contains a dozen obligations; at
                    # 1500 tokens the JSON array was being cut off mid-object and
                    # the whole chunk was discarded as unparseable.
                    max_tokens=self.settings.EXTRACTION_MAX_TOKENS,
                    messages=[
                        {
                            "role": "user",
                            "content": extraction_prompt
                        }
                    ]
                ),
                max_retries=self.settings.LLM_MAX_RETRIES,
                label=f"extraction[{section_hint[:30]}]",
            )

            response_text = message.content[0].text or ""

            # Parse JSON response. Smaller/free models routinely wrap output in
            # ```json fences or add prose, so strip that before giving up.
            obligations_data = self._parse_json_array(response_text)
            if obligations_data is None:
                logger.error(
                    f"Could not parse obligations JSON from model response: {response_text[:200]}"
                )
                self._record_failure(
                    f"Model returned unparseable output (not JSON): {response_text[:120]}"
                )
                return []
            
            # Convert to Obligation objects
            obligations = []
            for i, obl_data in enumerate(obligations_data):
                desc = obl_data.get("description", "")
                kw_list = obl_data.get("keywords", [])

                # ── Tier 3C: Explainability ───────────────────────────────
                _mandatory_triggers = ["shall", "must", "required", "obliged",
                                       "mandatory", "ensure", "maintain", "comply"]
                found_mandatory = [
                    kw for kw in _mandatory_triggers
                    if kw in desc.lower() or kw in obl_data.get("required_action", "").lower()
                ]
                confidence = 0.95 if found_mandatory else 0.70
                rationale = (
                    f"Extracted from {section_hint}. "
                    + (f"Contains mandatory language: {', '.join(found_mandatory[:3])}."
                       if found_mandatory else "Identified as a compliance requirement.")
                )

                # ── Evidence checklist from evidence_requirements ──────────
                from app.models.obligation import ChecklistItem
                ev_reqs = obl_data.get("evidence_requirements", [])
                checklist = [
                    ChecklistItem(
                        item_id=f"chk_{j}",
                        label=req,
                        completed=False,
                    )
                    for j, req in enumerate(ev_reqs)
                ]

                obligation = Obligation(
                    obligation_id=f"{circular_id}_obl_{len(obligations) + i}",
                    circular_id=circular_id,
                    clause_reference=obl_data.get(
                        "clause_reference",
                        f"{circular_title} — {section_hint}"
                    ),
                    title=obl_data.get("title", ""),
                    description=desc,
                    responsible_party=obl_data.get("responsible_party", ""),
                    required_action=obl_data.get("required_action", ""),
                    deadline=obl_data.get("deadline"),
                    deadline_type=obl_data.get("deadline_type", "not_specified"),
                    intermediary_types=obl_data.get("intermediary_types", intermediary_types),
                    conditions=obl_data.get("conditions", {}),
                    evidence_requirements=ev_reqs,
                    evidence_status=EvidenceStatus.MISSING,
                    keywords=kw_list,
                    severity=obl_data.get("severity", "medium"),
                    status=ObligationStatus.ACTIVE,
                    # explainability
                    extraction_rationale=rationale,
                    confidence_score=confidence,
                    mandatory_keywords=found_mandatory,
                    # checklist
                    evidence_checklist=checklist,
                )
                obligations.append(obligation)
            
            return obligations

        except LLMFatalError:
            # Bad model id / bad key — abort the whole run rather than repeating
            # the same doomed call for every remaining chunk.
            raise
        except LLMError as e:
            self._record_failure(str(e))
            return []
        except Exception as e:
            logger.error(f"Error extracting obligations from chunk: {str(e)}")
            self._record_failure(str(e))
            return []

    def _record_failure(self, message: str) -> None:
        """Track a failed chunk so the caller can report it instead of silently returning 0."""
        with self._counter_lock:
            self.chunks_failed += 1
            self.last_error = message

    @staticmethod
    def _parse_json_array(text: str):
        """
        Best-effort parse of a JSON array from a model response.
        Returns the parsed list, or None if nothing usable was found.
        """
        import re

        candidate = (text or "").strip()
        if not candidate:
            return None

        # Strip ```json ... ``` fences that instruction-tuned models like to add.
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
        if fence:
            candidate = fence.group(1).strip()

        for attempt in (candidate, None):
            if attempt is None:
                m = re.search(r'\[.*\]', candidate, re.DOTALL)
                if not m:
                    # No closed array at all — usually a truncated response.
                    # Fall through to the salvage pass rather than giving up.
                    break
                attempt = m.group()
            try:
                parsed = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return parsed
            # Some models wrap the array in {"obligations": [...]}
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        return v
                return []

        # Last resort: the response is a truncated array (the model hit its output
        # limit mid-object). Every *complete* object before the cut is still good
        # data — recovering them beats discarding the whole chunk.
        salvaged = ObligationExtractionAgent._salvage_objects(candidate)
        if salvaged:
            logger.warning(
                f"Recovered {len(salvaged)} complete obligation(s) from a truncated "
                f"model response ({len(candidate)} chars)."
            )
            return salvaged
        return None

    @staticmethod
    def _salvage_objects(text: str) -> list:
        """Parse every balanced top-level {...} object in a malformed JSON array."""
        objects = []
        depth = 0
        start = None
        in_string = False
        escaped = False

        for i, ch in enumerate(text):
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth:
                    depth -= 1
                    if depth == 0 and start is not None:
                        try:
                            obj = json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            pass
                        else:
                            if isinstance(obj, dict):
                                objects.append(obj)
                        start = None
        return objects

    def _link_obligation_relationships(self, obligations: List[Obligation]) -> List[Obligation]:
        """
        Identify relationships between obligations using Claude.
        """
        if len(obligations) < 2:
            return obligations
        
        # Build obligation summary for relationship detection
        obl_summaries = [
            f"{i}: {obl.title} (ID: {obl.obligation_id})"
            for i, obl in enumerate(obligations)
        ]
        
        relationship_prompt = f"""Given these compliance obligations extracted from a regulatory circular, identify which ones are related or dependent on each other.

Obligations:
{chr(10).join(obl_summaries)}

For each pair of obligations, determine if they are:
- INDEPENDENT: No relationship
- DEPENDENT: One must be completed before another
- CROSS_REFERENCE: They reference or build on each other
- CONFLICTING: They may contradict each other

Return a JSON object mapping obligation IDs to lists of related obligation IDs:
{{
  "obligation_id_1": ["obligation_id_2", "obligation_id_3"],
  "obligation_id_3": ["obligation_id_2"]
}}

Include only meaningful relationships. Return empty object {{}} if no relationships found.
Return ONLY valid JSON."""
        
        try:
            message = call_with_retry(
                lambda: self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[
                        {
                            "role": "user",
                            "content": relationship_prompt
                        }
                    ]
                ),
                max_retries=self.settings.LLM_MAX_RETRIES,
                label="relationship-linking",
            )

            response_text = message.content[0].text or ""
            relationships = json.loads(response_text.strip().strip("`"))

            # Apply relationships to obligations
            for obl in obligations:
                if obl.obligation_id in relationships:
                    obl.related_obligations = relationships[obl.obligation_id]

        except Exception as e:
            # Relationships are an enhancement, not core output — a failure here
            # degrades the graph but must not fail the run. Still surfaced to the
            # caller via last_error so it isn't invisible.
            logger.warning(f"Error linking obligation relationships: {str(e)}")
            self.last_error = self.last_error or f"relationship linking failed: {e}"

        return obligations
    
    def summarize_circular(self, circular_text: str) -> str:
        """Generate a summary of the circular."""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Provide a concise 2-3 sentence summary of this regulatory circular:

{circular_text[:2000]}...

Focus on the main regulatory requirements and key changes."""
                    }
                ]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error summarizing circular: {str(e)}")
            return "Summary generation failed"
