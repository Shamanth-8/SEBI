"""
Compliance dashboard and intermediary-specific endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

from app.api.circulars import orchestrator


@router.get("/dashboard/{intermediary_type}")
async def get_compliance_dashboard(intermediary_type: str):
    """
    Get comprehensive compliance dashboard for an intermediary type.
    Shows evidence gaps, severity breakdown, and action items.
    """
    try:
        dashboard = orchestrator.get_compliance_dashboard(intermediary_type)
        
        return {
            "intermediary_type": intermediary_type,
            "total_obligations": dashboard['total_obligations'],
            "not_applicable": dashboard['not_applicable'],
            "evidence_dashboard": dashboard['evidence_dashboard'],
            "severity_breakdown": dashboard['severity_breakdown'],
            "critical_gaps": dashboard['critical_gaps_count'],
            "action_items": dashboard['action_items_count']
        }
        
    except Exception as e:
        logger.error(f"Error generating compliance dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evidence-gaps/{intermediary_type}")
async def get_evidence_gaps(
    intermediary_type: str,
    severity: Optional[str] = Query(None)
):
    """
    Get color-coded evidence gaps for intermediary.
    Returns obligations grouped by evidence status (green/yellow/red).
    """
    try:
        gaps = orchestrator.graph.get_evidence_gaps()
        
        result = {
            "intermediary_type": intermediary_type,
            "complete": {
                "count": len(gaps['green']),
                "obligations": [
                    {
                        "id": o.obligation_id,
                        "title": o.title,
                        "severity": o.severity
                    }
                    for o in gaps['green']
                    if intermediary_type in o.intermediary_types
                ][:10]
            },
            "partial": {
                "count": len(gaps['yellow']),
                "obligations": [
                    {
                        "id": o.obligation_id,
                        "title": o.title,
                        "severity": o.severity
                    }
                    for o in gaps['yellow']
                    if intermediary_type in o.intermediary_types
                ][:10]
            },
            "missing": {
                "count": len(gaps['red']),
                "obligations": [
                    {
                        "id": o.obligation_id,
                        "title": o.title,
                        "severity": o.severity
                    }
                    for o in gaps['red']
                    if intermediary_type in o.intermediary_types
                ][:10]
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving evidence gaps: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mapping/{intermediary_type}")
async def get_compliance_mapping(intermediary_type: str):
    """Get obligations mapped to a specific intermediary type."""
    try:
        from app.agents.mapping_agent import ComplianceMappingAgent
        mapping_agent = ComplianceMappingAgent(orchestrator.graph)
        
        mapped = mapping_agent.map_obligations_to_intermediary(intermediary_type)
        
        return {
            "intermediary_type": intermediary_type,
            "applicable_obligations_count": len(mapped.applicable_obligations),
            "not_applicable_count": len(mapped.not_applicable_obligations),
            "critical_gaps_count": len(mapped.critical_gaps),
            "action_items": mapped.action_items[:20],  # Top 20
            "applicable_sample": [
                {
                    "id": o.obligation_id,
                    "title": o.title,
                    "severity": o.severity,
                    "deadline": o.deadline
                }
                for o in mapped.applicable_obligations[:10]
            ]
        }
        
    except Exception as e:
        logger.error(f"Error retrieving compliance mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
