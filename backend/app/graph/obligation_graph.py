"""Graph layer for managing the obligation dependency graph."""
"""
Obligation graph layer using NetworkX.
Manages nodes (obligations), edges (relationships), and persistence.
"""
import pickle
import logging
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
import networkx as nx
from app.models.obligation import Obligation, ObligationStatus, EvidenceStatus
from app.config import get_settings

logger = logging.getLogger(__name__)


class ObligationGraph:
    """
    Graph structure for managing compliance obligations and their relationships.
    """
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.settings = get_settings()
        self.obligation_map = {}  # obligation_id -> Obligation
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        import os
        os.makedirs(self.settings.DATA_DIR, exist_ok=True)
    
    def add_obligation(self, obligation: Obligation) -> None:
        """Add an obligation as a node to the graph."""
        self.graph.add_node(
            obligation.obligation_id,
            obligation=obligation,
            status=obligation.status,
            evidence_status=obligation.evidence_status,
            severity=obligation.severity,
            updated_at=obligation.updated_at
        )
        self.obligation_map[obligation.obligation_id] = obligation
    
    def add_obligations(self, obligations: List[Obligation]) -> None:
        """Add multiple obligations to the graph."""
        for obligation in obligations:
            self.add_obligation(obligation)
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str = "depends_on",
        weight: float = 1.0
    ) -> None:
        """
        Add an edge between two obligations.
        
        Args:
            source_id: Source obligation ID
            target_id: Target obligation ID
            edge_type: Type of relationship (depends_on, supersedes, cross_reference)
            weight: Edge weight for impact calculation
        """
        self.graph.add_edge(
            source_id,
            target_id,
            edge_type=edge_type,
            weight=weight
        )
    
    def get_obligation(self, obligation_id: str) -> Optional[Obligation]:
        """Retrieve an obligation by ID."""
        return self.obligation_map.get(obligation_id)
    
    def get_all_obligations(self) -> List[Obligation]:
        """Get all obligations in the graph."""
        return list(self.obligation_map.values())
    
    def get_dependent_obligations(self, obligation_id: str) -> List[str]:
        """Get all obligations that depend on this one."""
        return list(self.graph.successors(obligation_id))
    
    def get_dependencies(self, obligation_id: str) -> List[str]:
        """Get all obligations this one depends on."""
        return list(self.graph.predecessors(obligation_id))
    
    def get_transitive_dependents(self, obligation_id: str) -> Set[str]:
        """
        Get all obligations indirectly affected by changes to this obligation
        (transitive closure of dependents).
        """
        dependents = set()
        to_visit = list(self.graph.successors(obligation_id))
        visited = set()
        
        while to_visit:
            current = to_visit.pop(0)
            if current in visited:
                continue
            visited.add(current)
            dependents.add(current)
            
            for successor in self.graph.successors(current):
                if successor not in visited:
                    to_visit.append(successor)
        
        return dependents
    
    def update_obligation(
        self,
        obligation_id: str,
        updates: Dict
    ) -> Optional[Obligation]:
        """Update an obligation's attributes."""
        if obligation_id not in self.obligation_map:
            logger.warning(f"Obligation {obligation_id} not found")
            return None
        
        obligation = self.obligation_map[obligation_id]
        
        # Update attributes
        for key, value in updates.items():
            if hasattr(obligation, key):
                setattr(obligation, key, value)
        
        obligation.updated_at = datetime.now()
        
        # Update graph node attributes
        self.graph.nodes[obligation_id]['obligation'] = obligation
        self.graph.nodes[obligation_id]['updated_at'] = obligation.updated_at
        
        return obligation
    
    def mark_superseded(
        self,
        obligation_id: str,
        superseded_by: List[str]
    ) -> None:
        """Mark an obligation as superseded."""
        obligation = self.get_obligation(obligation_id)
        if obligation:
            obligation.status = ObligationStatus.SUPERSEDED
            obligation.superseded_by = superseded_by
            self.update_obligation(obligation_id, {
                'status': ObligationStatus.SUPERSEDED,
                'superseded_by': superseded_by
            })
    
    def get_evidence_gaps(self) -> Dict[str, List[Obligation]]:
        """
        Group obligations by evidence status.
        
        Returns:
            Dict mapping evidence status to list of obligations
        """
        gaps = {
            'green': [],
            'yellow': [],
            'red': []
        }
        
        for obligation in self.obligation_map.values():
            status_key = obligation.evidence_status.value
            gaps[status_key].append(obligation)
        
        return gaps
    
    def get_by_circular(self, circular_id: str) -> List[Obligation]:
        """Get all obligations from a specific circular."""
        return [
            obl for obl in self.obligation_map.values()
            if obl.circular_id == circular_id
        ]
    
    def search_obligations(
        self,
        query: str,
        intermediary_type: Optional[str] = None
    ) -> List[Obligation]:
        """
        Search obligations by keywords, title, or description.
        """
        results = []
        query_lower = query.lower()
        
        for obligation in self.obligation_map.values():
            # Check if query matches
            if (query_lower in obligation.title.lower() or
                query_lower in obligation.description.lower() or
                any(query_lower in kw.lower() for kw in obligation.keywords)):
                
                # Filter by intermediary type if specified
                if intermediary_type is None or intermediary_type in obligation.intermediary_types:
                    results.append(obligation)
        
        return results
    
    def get_workflow_obligations(
        self,
        workflow_name: str
    ) -> List[Obligation]:
        """Get obligations related to a specific workflow."""
        # Workflows could be: margin_reporting, risk_management, audit_trail, etc.
        results = []
        
        for obligation in self.obligation_map.values():
            if any(workflow_name.lower() in kw.lower() for kw in obligation.keywords):
                results.append(obligation)
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get graph statistics."""
        evidence_gaps = self.get_evidence_gaps()
        
        return {
            'total_obligations': len(self.obligation_map),
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'active_obligations': len([
                o for o in self.obligation_map.values()
                if o.status == ObligationStatus.ACTIVE
            ]),
            'superseded_obligations': len([
                o for o in self.obligation_map.values()
                if o.status == ObligationStatus.SUPERSEDED
            ]),
            'evidence_gaps': {
                'complete': len(evidence_gaps['green']),
                'partial': len(evidence_gaps['yellow']),
                'missing': len(evidence_gaps['red'])
            },
            'high_severity_count': len([
                o for o in self.obligation_map.values()
                if o.severity == 'high'
            ]),
            'circulars_ingested': len(set(o.circular_id for o in self.obligation_map.values()))
        }
    
    def save(self, path: Optional[str] = None) -> None:
        """Persist graph to disk."""
        path = path or self.settings.GRAPH_DB_PATH
        
        try:
            with open(path, 'wb') as f:
                pickle.dump({
                    'graph': self.graph,
                    'obligation_map': self.obligation_map
                }, f)
            logger.info(f"Graph saved to {path}")
        except Exception as e:
            logger.error(f"Error saving graph: {str(e)}")
    
    def load(self, path: Optional[str] = None) -> None:
        """Load graph from disk."""
        path = path or self.settings.GRAPH_DB_PATH
        
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.graph = data['graph']
                self.obligation_map = data['obligation_map']
            logger.info(f"Graph loaded from {path}")
        except FileNotFoundError:
            logger.warning(f"No saved graph found at {path}. Starting with empty graph.")
        except Exception as e:
            logger.error(f"Error loading graph: {str(e)}")
