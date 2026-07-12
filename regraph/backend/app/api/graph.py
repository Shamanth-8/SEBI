"""
Graph analysis and statistics endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

from app.agents.orchestrator import RegGraphOrchestrator
orchestrator = RegGraphOrchestrator()


@router.get("/statistics")
async def get_graph_statistics():
    """
    Get overall graph statistics.
    Shows total obligations, relationships, evidence gaps, etc.
    """
    try:
        stats = orchestrator.get_graph_statistics()
        
        return {
            "total_obligations": stats['total_obligations'],
            "total_nodes": stats['total_nodes'],
            "total_edges": stats['total_edges'],
            "active_obligations": stats['active_obligations'],
            "superseded_obligations": stats['superseded_obligations'],
            "evidence_gaps": stats['evidence_gaps'],
            "high_severity_count": stats['high_severity_count'],
            "circulars_ingested": stats['circulars_ingested'],
            "network_density": stats['total_edges'] / max(stats['total_nodes'], 1)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving graph statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dependencies/{obligation_id}")
async def get_obligation_dependencies(obligation_id: str):
    """
    Get dependency information for an obligation.
    Shows what it depends on and what depends on it.
    """
    try:
        obligation = orchestrator.graph.get_obligation(obligation_id)
        
        if not obligation:
            raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
        
        dependencies = orchestrator.graph.get_dependencies(obligation_id)
        dependents = orchestrator.graph.get_dependent_obligations(obligation_id)
        transitive_dependents = orchestrator.graph.get_transitive_dependents(obligation_id)
        
        return {
            "obligation_id": obligation_id,
            "obligation_title": obligation.title,
            "direct_dependencies": dependencies,
            "direct_dependents": dependents,
            "transitive_dependents": list(transitive_dependents),
            "dependency_count": len(dependencies),
            "dependent_count": len(dependents),
            "transitive_dependent_count": len(transitive_dependents)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving dependencies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/{obligation_id}")
async def analyze_impact(
    obligation_id: str,
    depth: int = Query(2, ge=1, le=5)
):
    """
    Analyze the impact of changing an obligation.
    Shows all affected downstream obligations.
    """
    try:
        from app.agents.impact_propagation import ImpactPropagationEngine
        impact_engine = ImpactPropagationEngine(orchestrator.graph)
        
        propagation = impact_engine.propagate_impact([obligation_id])
        critical_deps = impact_engine.get_critical_dependencies(obligation_id, depth)
        effort = impact_engine.calculate_implementation_effort([obligation_id])
        
        return {
            "obligation_id": obligation_id,
            "directly_affected": propagation['directly_affected'],
            "indirectly_affected": propagation['indirectly_affected'],
            "affected_workflows": propagation['affected_workflows'],
            "total_affected": propagation['total_affected_count'],
            "critical_dependencies": critical_deps['critical_dependencies'],
            "implementation_effort": effort
        }
        
    except Exception as e:
        logger.error(f"Error analyzing impact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/json")
async def export_graph_json():
    """
    Export the entire obligation graph as JSON.
    Useful for visualization and analysis.
    """
    try:
        obligations = orchestrator.graph.get_all_obligations()
        
        nodes = [
            {
                "id": o.obligation_id,
                "label": o.title,
                "status": o.status,
                "severity": o.severity,
                "evidence_status": o.evidence_status.value,
                "evidence_count": len([o.evidence_requirements])
            }
            for o in obligations
        ]
        
        edges = []
        for obl_id in orchestrator.graph.graph.nodes():
            for target in orchestrator.graph.graph.successors(obl_id):
                edges.append({
                    "source": obl_id,
                    "target": target,
                    "type": orchestrator.graph.graph[obl_id][target].get('edge_type', 'related')
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges)
        }
        
    except Exception as e:
        logger.error(f"Error exporting graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
