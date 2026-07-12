"""
Impact propagation engine for analyzing ripple effects through obligation graph.
"""
import logging
from typing import List, Set, Dict, Tuple
from app.models.obligation import Obligation
from app.graph.obligation_graph import ObligationGraph

logger = logging.getLogger(__name__)


class ImpactPropagationEngine:
    """
    Analyzes how changes to obligations propagate through the dependency graph.
    """
    
    def __init__(self, obligation_graph: ObligationGraph):
        self.graph = obligation_graph
    
    def propagate_impact(
        self,
        changed_obligation_ids: List[str],
        impact_type: str = "modified"  # new, modified, superseded
    ) -> Dict:
        """
        Propagate impact of changed obligations through the graph.
        
        Args:
            changed_obligation_ids: IDs of obligations that changed
            impact_type: Type of change
            
        Returns:
            Dict with directly and indirectly affected obligations
        """
        directly_affected = set()
        indirectly_affected = set()
        dependency_chain = {}
        
        # For each changed obligation
        for obl_id in changed_obligation_ids:
            # Get directly dependent obligations
            dependents = self.graph.get_dependent_obligations(obl_id)
            directly_affected.update(dependents)
            
            # Get transitively dependent obligations
            transitive = self.graph.get_transitive_dependents(obl_id)
            indirectly_affected.update(transitive - set(dependents))
            
            # Build dependency chain
            dependency_chain[obl_id] = list(transitive)
            
            logger.info(f"Obligation {obl_id}: {len(dependents)} direct dependents, {len(transitive)} transitive")
        
        # Identify affected workflows
        affected_workflows = self._identify_affected_workflows(
            list(directly_affected | indirectly_affected)
        )
        
        return {
            'directly_affected': list(directly_affected),
            'indirectly_affected': list(indirectly_affected),
            'affected_workflows': affected_workflows,
            'dependency_chain': dependency_chain,
            'total_affected_count': len(directly_affected) + len(indirectly_affected)
        }
    
    def _identify_affected_workflows(self, obligation_ids: List[str]) -> List[str]:
        """Identify which compliance workflows are affected."""
        workflows = set()
        
        for obl_id in obligation_ids:
            obligation = self.graph.get_obligation(obl_id)
            if obligation:
                # Extract workflow keywords from keywords
                for keyword in obligation.keywords:
                    if any(wf in keyword.lower() for wf in [
                        'margin', 'reporting', 'risk', 'management', 'audit',
                        'trail', 'customer', 'kyc', 'grievance', 'compliance'
                    ]):
                        workflows.add(keyword)
        
        return list(workflows)
    
    def get_impact_score(
        self,
        changed_obligation_ids: List[str],
        existing_obligations_count: int
    ) -> float:
        """
        Calculate impact score (0-1) based on number affected.
        """
        propagation = self.propagate_impact(changed_obligation_ids)
        total_affected = propagation['total_affected_count']
        
        if existing_obligations_count == 0:
            return 1.0  # All new = full impact
        
        impact_ratio = total_affected / existing_obligations_count
        return min(impact_ratio, 1.0)
    
    def get_critical_dependencies(
        self,
        obligation_id: str,
        depth: int = 2
    ) -> Dict:
        """
        Get critical dependencies for a specific obligation.
        """
        dependencies = []
        visited = set()
        
        def traverse(obl_id: str, current_depth: int):
            if current_depth >= depth or obl_id in visited:
                return
            
            visited.add(obl_id)
            deps = self.graph.get_dependencies(obl_id)
            
            for dep_id in deps:
                dep_obl = self.graph.get_obligation(dep_id)
                if dep_obl:
                    dependencies.append({
                        'obligation_id': dep_id,
                        'title': dep_obl.title,
                        'severity': dep_obl.severity,
                        'depth': current_depth
                    })
                    traverse(dep_id, current_depth + 1)
        
        traverse(obligation_id, 0)
        
        return {
            'obligation_id': obligation_id,
            'critical_dependencies': sorted(
                dependencies,
                key=lambda x: x['depth']
            ),
            'dependency_count': len(dependencies)
        }
    
    def get_impact_timeline(
        self,
        changed_obligation_ids: List[str]
    ) -> List[Dict]:
        """
        Generate a timeline of when obligations must be addressed
        based on deadlines of affected obligations.
        """
        timeline = []
        propagation = self.propagate_impact(changed_obligation_ids)
        
        affected_ids = (
            set(propagation['directly_affected']) |
            set(propagation['indirectly_affected'])
        )
        
        # Group by deadline
        deadline_groups = {}
        for obl_id in affected_ids:
            obligation = self.graph.get_obligation(obl_id)
            if obligation and obligation.deadline:
                deadline = obligation.deadline
                if deadline not in deadline_groups:
                    deadline_groups[deadline] = []
                deadline_groups[deadline].append(obligation)
        
        # Sort by deadline
        for deadline in sorted(deadline_groups.keys()):
            obls = deadline_groups[deadline]
            timeline.append({
                'deadline': deadline,
                'obligation_count': len(obls),
                'obligations': [
                    {
                        'id': obl.obligation_id,
                        'title': obl.title,
                        'severity': obl.severity
                    }
                    for obl in obls
                ]
            })
        
        return timeline
    
    def calculate_implementation_effort(
        self,
        changed_obligation_ids: List[str]
    ) -> Dict:
        """
        Estimate implementation effort for addressing impact.
        """
        propagation = self.propagate_impact(changed_obligation_ids)
        affected_ids = (
            set(propagation['directly_affected']) |
            set(propagation['indirectly_affected'])
        )
        
        # Categorize by effort level
        effort_categories = {
            'high_effort': [],      # Changes to infrastructure/systems
            'medium_effort': [],    # Changes to processes/procedures
            'low_effort': []        # Informational/documentation updates
        }
        
        for obl_id in affected_ids:
            obligation = self.graph.get_obligation(obl_id)
            if obligation:
                if any(x in obligation.description.lower() for x in ['system', 'infrastructure', 'technology']):
                    effort_categories['high_effort'].append(obl_id)
                elif any(x in obligation.description.lower() for x in ['process', 'procedure', 'workflow']):
                    effort_categories['medium_effort'].append(obl_id)
                else:
                    effort_categories['low_effort'].append(obl_id)
        
        return {
            'high_effort_count': len(effort_categories['high_effort']),
            'medium_effort_count': len(effort_categories['medium_effort']),
            'low_effort_count': len(effort_categories['low_effort']),
            'total_effort_estimate': (
                len(effort_categories['high_effort']) * 3 +
                len(effort_categories['medium_effort']) * 2 +
                len(effort_categories['low_effort']) * 1
            ),
            'effort_breakdown': effort_categories
        }
