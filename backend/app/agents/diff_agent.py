"""
Semantic diff agent for comparing new obligations against existing graph.
"""
import json
import logging
from typing import List, Dict, Tuple
from app.models.obligation import Obligation, DiffResult
from app.graph.obligation_graph import ObligationGraph
from app.config import get_settings
from app.anthropic_adapter import create_anthropic_compatible_client

logger = logging.getLogger(__name__)


class SemanticDiffAgent:
    """
    Agent that performs semantic diffing between new and existing obligations
    using Claude to understand meaning, not just text matching.
    Works with both Anthropic and OpenRouter providers.
    """
    
    def __init__(self, obligation_graph: ObligationGraph):
        settings = get_settings()
        self.settings = settings
        self.model = self.settings.LLM_MODEL
        self.graph = obligation_graph
        # Built on first use, not here: constructing it eagerly makes the whole
        # application fail to import when no API key is configured, which defeats
        # the offline path entirely (the container would not even start).
        self._client = None
        logger.info(f"Initialized diff agent with provider: {settings.LLM_PROVIDER}, model: {self.model}")

    @property
    def client(self):
        if self._client is None:
            self._client = create_anthropic_compatible_client(self.settings.LLM_PROVIDER)
        return self._client
    
    def diff_obligations(
        self,
        new_obligations: List[Obligation],
        existing_obligations: List[Obligation] = None
    ) -> DiffResult:
        """
        Compare new obligations against existing ones.
        
        Returns:
            DiffResult containing new, modified, and superseded obligations
        """
        if existing_obligations is None:
            existing_obligations = self.graph.get_all_obligations()
        
        if not existing_obligations:
            # All obligations are new if graph is empty
            logger.info("No existing obligations. All incoming obligations are new.")
            return DiffResult(
                new_obligations=new_obligations,
                impact_score=1.0
            )
        
        logger.info(f"Performing semantic diff: {len(new_obligations)} new vs {len(existing_obligations)} existing")

        # EXTRACTION_MODE=ml means "no network calls anywhere in the pipeline".
        # Going straight to the lexical diff keeps that promise (and is far faster
        # than waiting for calls that are only going to fail).
        from app.config import get_settings
        if (get_settings().EXTRACTION_MODE or "").lower() == "ml":
            logger.info("EXTRACTION_MODE=ml — using the deterministic lexical diff")
            return self.lexical_diff(new_obligations, existing_obligations)

        # Call Claude to perform semantic matching
        new_obl_summaries = self._prepare_obligation_summaries(new_obligations)
        existing_obl_summaries = self._prepare_obligation_summaries(existing_obligations)
        
        diff_result = self._semantic_diff(
            new_obl_summaries,
            existing_obl_summaries,
            new_obligations,
            existing_obligations
        )

        # The LLM diff returns an empty result on any failure (quota, bad JSON).
        # Reporting "0 new, 0 modified" for a circular that clearly contains
        # obligations is worse than useless — it looks like a successful no-op.
        # Fall back to a deterministic lexical diff so the pipeline still tells
        # the truth about what changed.
        if not (diff_result.new_obligations or diff_result.modified_obligations
                or diff_result.superseded_obligations):
            logger.warning(
                "Semantic diff produced no classification — falling back to lexical diff"
            )
            diff_result = self.lexical_diff(new_obligations, existing_obligations)

        return diff_result

    # ── Deterministic fallback ───────────────────────────────────────────────

    def lexical_diff(
        self,
        new_obligations: List[Obligation],
        existing_obligations: List[Obligation],
        modified_at: float = 0.62,
        duplicate_at: float = 0.92,
    ) -> DiffResult:
        """
        Classify NEW / MODIFIED without an LLM, using TF-IDF cosine similarity
        over the clause text.

        Thresholds: above `duplicate_at` the clause is a restatement of one already
        in the graph (a re-upload of the same circular) and is not reported as a
        change; between the two it is a MODIFIED version of its closest match, with
        the changed fields computed by direct comparison; below, it is NEW.
        """
        result = DiffResult()
        if not new_obligations:
            return result
        if not existing_obligations:
            result.new_obligations = list(new_obligations)
            result.impact_score = 1.0
            return result

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            logger.warning("scikit-learn unavailable — treating every obligation as NEW")
            result.new_obligations = list(new_obligations)
            result.impact_score = 1.0
            return result

        new_texts = [f"{o.title} {o.description}" for o in new_obligations]
        old_texts = [f"{o.title} {o.description}" for o in existing_obligations]
        try:
            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                  sublinear_tf=True).fit(new_texts + old_texts)
            sim = cosine_similarity(vec.transform(new_texts), vec.transform(old_texts))
        except ValueError:
            result.new_obligations = list(new_obligations)
            result.impact_score = 1.0
            return result

        duplicates = 0
        for i, obl in enumerate(new_obligations):
            j = int(sim[i].argmax())
            score = float(sim[i, j])
            match = existing_obligations[j]

            if score >= duplicate_at:
                duplicates += 1
                continue
            if score >= modified_at:
                changes = self._field_changes(match, obl)
                if not changes:
                    duplicates += 1
                    continue
                result.modified_obligations.append({
                    "old_id": match.obligation_id,
                    "new_obligation": obl,
                    "changes": changes,
                    "similarity": round(score, 3),
                    "method": "lexical",
                })
            else:
                result.new_obligations.append(obl)

        total = len(new_obligations) or 1
        result.impact_score = round(
            min(1.0, (len(result.new_obligations) + 0.5 * len(result.modified_obligations))
                / total), 3
        )
        logger.info(
            f"Lexical diff: {len(result.new_obligations)} new, "
            f"{len(result.modified_obligations)} modified, {duplicates} unchanged"
        )
        return result

    @staticmethod
    def _field_changes(old: Obligation, new: Obligation) -> List[str]:
        """Human-readable list of what actually differs between two obligations."""
        changes = []
        if (old.deadline or "") != (new.deadline or ""):
            changes.append(f"deadline: '{old.deadline or 'none'}' → '{new.deadline or 'none'}'")
        if (old.deadline_type or "") != (new.deadline_type or ""):
            changes.append(f"deadline type: {old.deadline_type} → {new.deadline_type}")
        if old.severity != new.severity:
            changes.append(f"severity: {old.severity} → {new.severity}")
        if (old.responsible_party or "") != (new.responsible_party or ""):
            changes.append(
                f"responsible party: '{old.responsible_party}' → '{new.responsible_party}'")
        added_types = set(new.intermediary_types) - set(old.intermediary_types)
        removed_types = set(old.intermediary_types) - set(new.intermediary_types)
        if added_types:
            changes.append(f"now also applies to: {', '.join(sorted(added_types))}")
        if removed_types:
            changes.append(f"no longer applies to: {', '.join(sorted(removed_types))}")
        added_ev = set(new.evidence_requirements) - set(old.evidence_requirements)
        if added_ev:
            changes.append(f"new evidence required: {', '.join(sorted(added_ev)[:2])}")
        return changes
    
    def _prepare_obligation_summaries(self, obligations: List[Obligation]) -> str:
        """Prepare obligation summaries for LLM analysis."""
        summaries = []
        for obl in obligations:
            summary = f"""ID: {obl.obligation_id}
Title: {obl.title}
Description: {obl.description}
Action: {obl.required_action}
Deadline: {obl.deadline or 'Not specified'}
Responsible: {obl.responsible_party}"""
            summaries.append(summary)
        
        return "\n---\n".join(summaries)
    
    def _semantic_diff(
        self,
        new_summaries: str,
        existing_summaries: str,
        new_obligations: List[Obligation],
        existing_obligations: List[Obligation]
    ) -> DiffResult:
        """Use Claude to perform semantic diff."""
        
        prompt = f"""You are a regulatory compliance expert. Your task is to compare new regulatory obligations against existing ones and determine:
1. Which new obligations are genuinely NEW (not covered by existing)
2. Which new obligations MODIFY existing ones
3. Which new obligations SUPERSEDE existing ones
4. Calculate overall impact score

EXISTING OBLIGATIONS:
---
{existing_summaries}
---

NEW OBLIGATIONS (from latest circular):
---
{new_summaries}
---

For each new obligation, determine its relationship to existing ones. Consider semantic similarity:
- Same requirement with updated deadline = MODIFY
- Same requirement with relaxed conditions = MODIFY
- Requirement that explicitly says "replaces" or "amends" = SUPERSEDE
- No equivalent requirement = NEW

Return JSON with this structure:
{{
  "new": [list of new obligation IDs from NEW OBLIGATIONS],
  "modified": [
    {{
      "new_id": "ID from NEW",
      "existing_id": "ID from EXISTING",
      "changes": ["change description 1", "change description 2"]
    }}
  ],
  "superseded": [list of EXISTING obligation IDs that are now superseded],
  "impact_score": 0.0 to 1.0,
  "impact_rationale": "Brief explanation of impact score"
}}

Be precise. Only mark as NEW if truly novel. Return ONLY valid JSON."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response_text = message.content[0].text
            diff_data = json.loads(response_text)
            
            # Build DiffResult
            result = DiffResult()
            
            # Add new obligations
            new_ids = diff_data.get("new", [])
            for obl in new_obligations:
                if obl.obligation_id in new_ids:
                    result.new_obligations.append(obl)
            
            # Add modified obligations
            for mod in diff_data.get("modified", []):
                new_id = mod.get("new_id")
                existing_id = mod.get("existing_id")
                changes = mod.get("changes", [])
                
                new_obl = next((o for o in new_obligations if o.obligation_id == new_id), None)
                if new_obl:
                    result.modified_obligations.append({
                        "old_id": existing_id,
                        "new_obligation": new_obl,
                        "changes": changes
                    })
            
            # Add superseded obligations
            result.superseded_obligations = diff_data.get("superseded", [])
            
            # Set impact score
            result.impact_score = diff_data.get("impact_score", 0.5)
            
            logger.info(f"Diff complete: {len(result.new_obligations)} new, {len(result.modified_obligations)} modified, {len(result.superseded_obligations)} superseded")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse diff response: {str(e)}")
            return DiffResult()
        except Exception as e:
            logger.error(f"Error in semantic diff: {str(e)}")
            return DiffResult()
    
    def identify_amendments(
        self,
        new_obligations: List[Obligation]
    ) -> Dict[str, List[str]]:
        """
        Identify which existing obligations each new one amends.
        
        Returns:
            Mapping of new obligation IDs to list of amended obligation IDs
        """
        amendments = {}
        
        prompt = f"""Given these new obligations, identify which ones explicitly amend or modify previous obligations.

NEW OBLIGATIONS:
{self._prepare_obligation_summaries(new_obligations)}

For each obligation, extract any reference to what it amends (e.g., "amends clause 3.1", "replaces paragraph 2.2").

Return JSON mapping obligation IDs to lists of clause references they amend:
{{
  "obligation_id_1": ["clause_3.1", "section_2.2"],
  "obligation_id_2": []
}}

Return ONLY valid JSON."""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            amendments = json.loads(message.content[0].text)
        except Exception as e:
            logger.warning(f"Error identifying amendments: {str(e)}")
        
        return amendments
