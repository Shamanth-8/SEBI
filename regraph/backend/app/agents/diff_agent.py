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
        self.client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
        self.settings = settings
        self.model = self.settings.LLM_MODEL
        self.graph = obligation_graph
        logger.info(f"Initialized diff agent with provider: {settings.LLM_PROVIDER}, model: {self.model}")
    
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
        
        # Call Claude to perform semantic matching
        new_obl_summaries = self._prepare_obligation_summaries(new_obligations)
        existing_obl_summaries = self._prepare_obligation_summaries(existing_obligations)
        
        diff_result = self._semantic_diff(
            new_obl_summaries,
            existing_obl_summaries,
            new_obligations,
            existing_obligations
        )
        
        return diff_result
    
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
                max_tokens=4096,
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
