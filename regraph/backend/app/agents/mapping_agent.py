"""
Compliance mapping agent for associating obligations to intermediary profiles.
"""
import json
import logging
from typing import List, Dict, Optional
from app.models.obligation import Obligation, ComplianceMapResult, EvidenceStatus
from app.graph.obligation_graph import ObligationGraph
from app.config import get_settings
from app.anthropic_adapter import create_anthropic_compatible_client

logger = logging.getLogger(__name__)


class ComplianceMappingAgent:
    """
    Maps obligations to specific intermediary profiles (stockbroker, RTA, investment adviser).
    Determines which obligations apply to which entity type and generates action items.
    Works with both Anthropic and OpenRouter providers.
    """
    
    def __init__(self, obligation_graph: ObligationGraph):
        settings = get_settings()
        self.client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
        self.settings = settings
        self.model = self.settings.LLM_MODEL
        self.graph = obligation_graph
        logger.info(f"Initialized mapping agent with provider: {settings.LLM_PROVIDER}, model: {self.model}")
        
        # Intermediary type profiles
        self.intermediary_profiles = {
            'stockbroker': {
                'description': 'Stock exchange member stockbroker',
                'key_activities': ['trading', 'settlement', 'clearing', 'margin management']
            },
            'rta': {
                'description': 'Registrar and Transfer Agent',
                'key_activities': ['shareholder management', 'dividend processing', 'share transfer']
            },
            'investment_adviser': {
                'description': 'SEBI-registered investment adviser',
                'key_activities': ['advice', 'portfolio management', 'client communication']
            }
        }
    
    def map_obligations_to_intermediary(
        self,
        intermediary_type: str,
        obligations: Optional[List[Obligation]] = None,
        custom_conditions: Optional[Dict] = None
    ) -> ComplianceMapResult:
        """
        Map obligations to a specific intermediary type.
        
        Args:
            intermediary_type: Type of intermediary (stockbroker, rta, investment_adviser)
            obligations: List of obligations to map (defaults to all)
            custom_conditions: Custom applicability conditions (AUM threshold, etc.)
            
        Returns:
            ComplianceMapResult with applicable obligations and action items
        """
        if obligations is None:
            obligations = self.graph.get_all_obligations()
        
        logger.info(f"Mapping {len(obligations)} obligations to {intermediary_type}")
        
        # Filter obligations applicable to this intermediary type
        applicable = [
            obl for obl in obligations
            if intermediary_type in obl.intermediary_types
        ]
        
        # Use Claude to refine applicability
        refined_applicable, not_applicable = self._refine_applicability(
            intermediary_type,
            applicable,
            custom_conditions
        )
        
        # Generate action items
        action_items = self._generate_action_items(
            intermediary_type,
            refined_applicable
        )
        
        # Identify critical gaps
        critical_gaps = [
            {
                'obligation_id': obl.obligation_id,
                'title': obl.title,
                'severity': obl.severity,
                'gap_type': 'evidence' if obl.evidence_status == EvidenceStatus.MISSING else 'process'
            }
            for obl in refined_applicable
            if obl.severity == 'high' and obl.evidence_status != EvidenceStatus.COMPLETE
        ]
        
        not_applicable_ids = [obl.obligation_id for obl in not_applicable]
        
        result = ComplianceMapResult(
            intermediary_type=intermediary_type,
            applicable_obligations=refined_applicable,
            not_applicable_obligations=not_applicable_ids,
            critical_gaps=critical_gaps,
            action_items=action_items
        )
        
        logger.info(f"Mapped {len(refined_applicable)} applicable obligations for {intermediary_type}")
        return result
    
    def _refine_applicability(
        self,
        intermediary_type: str,
        obligations: List[Obligation],
        custom_conditions: Optional[Dict] = None
    ) -> tuple[List[Obligation], List[Obligation]]:
        """Use Claude to refine applicability of obligations."""
        
        profile = self.intermediary_profiles.get(intermediary_type, {})
        obl_summaries = "\n".join([
            f"- {obl.obligation_id}: {obl.title} ({obl.description[:100]}...)"
            for obl in obligations[:10]  # Limit for token budget
        ])
        
        prompt = f"""You are a regulatory compliance expert. Determine which obligations apply to a {intermediary_type}.

INTERMEDIARY PROFILE:
{profile.get('description', '')}
Key activities: {', '.join(profile.get('key_activities', []))}

CUSTOM CONDITIONS:
{json.dumps(custom_conditions or {}, indent=2)}

OBLIGATIONS TO ASSESS:
{obl_summaries}

For each obligation, decide if it applies to this intermediary type. Consider:
1. Is this intermediary type mentioned or implied?
2. Are the required activities relevant to this intermediary?
3. Do custom conditions (AUM, client count, etc.) affect applicability?
4. Are there any exemptions mentioned?

Return JSON:
{{
  "applicable": ["obligation_id_1", "obligation_id_2"],
  "not_applicable": ["obligation_id_3"],
  "reasoning": {{
    "obligation_id_1": "Why it applies"
  }}
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
            
            response = json.loads(message.content[0].text)
            applicable_ids = set(response.get('applicable', []))
            
            applicable_obls = [obl for obl in obligations if obl.obligation_id in applicable_ids]
            not_applicable_obls = [obl for obl in obligations if obl.obligation_id not in applicable_ids]
            
            return applicable_obls, not_applicable_obls
            
        except Exception as e:
            logger.warning(f"Error refining applicability: {str(e)}. Returning defaults.")
            return obligations, []
    
    def _generate_action_items(
        self,
        intermediary_type: str,
        obligations: List[Obligation]
    ) -> List[Dict]:
        """Generate prioritized action items for the intermediary."""
        
        action_items = []
        
        # Group by responsible party
        by_party = {}
        for obl in obligations:
            party = obl.responsible_party
            if party not in by_party:
                by_party[party] = []
            by_party[party].append(obl)
        
        # Generate action items for each party
        for party, obls in by_party.items():
            # Sort by severity and deadline
            sorted_obls = sorted(
                obls,
                key=lambda x: (x.severity != 'high', x.deadline or '')
            )
            
            for i, obl in enumerate(sorted_obls):
                action_item = {
                    'priority': 'critical' if obl.severity == 'high' else 'normal',
                    'responsible_party': party,
                    'action': obl.required_action,
                    'deadline': obl.deadline or 'To be determined',
                    'evidence_needed': obl.evidence_requirements,
                    'obligation_id': obl.obligation_id,
                    'estimated_effort': self._estimate_effort(obl),
                    'dependencies': obl.related_obligations[:3]  # Top 3 dependencies
                }
                action_items.append(action_item)
        
        return action_items
    
    def _estimate_effort(self, obligation: Obligation) -> str:
        """Estimate effort required to implement an obligation."""
        keywords = obligation.description.lower()
        
        if any(x in keywords for x in ['system', 'infrastructure', 'technology', 'development']):
            return 'high'
        elif any(x in keywords for x in ['process', 'procedure', 'review', 'approval']):
            return 'medium'
        else:
            return 'low'
    
    def get_intermediary_compliance_dashboard(
        self,
        intermediary_type: str
    ) -> Dict:
        """Get comprehensive compliance dashboard for an intermediary."""
        
        mapped = self.map_obligations_to_intermediary(intermediary_type)
        
        # Evidence dashboard
        evidence_stats = {
            'complete': 0,
            'partial': 0,
            'missing': 0
        }
        
        for obl in mapped.applicable_obligations:
            status = obl.evidence_status.value
            if status == 'green':
                evidence_stats['complete'] += 1
            elif status == 'yellow':
                evidence_stats['partial'] += 1
            else:
                evidence_stats['missing'] += 1
        
        # Severity breakdown
        severity_breakdown = {
            'critical': len([o for o in mapped.applicable_obligations if o.severity == 'high']),
            'normal': len([o for o in mapped.applicable_obligations if o.severity == 'medium']),
            'low': len([o for o in mapped.applicable_obligations if o.severity == 'low'])
        }
        
        return {
            'intermediary_type': intermediary_type,
            'total_obligations': len(mapped.applicable_obligations),
            'not_applicable': len(mapped.not_applicable_obligations),
            'evidence_dashboard': evidence_stats,
            'severity_breakdown': severity_breakdown,
            'critical_gaps_count': len(mapped.critical_gaps),
            'action_items_count': len(mapped.action_items),
            'next_steps': mapped.priority_actions if hasattr(mapped, 'priority_actions') else []
        }
