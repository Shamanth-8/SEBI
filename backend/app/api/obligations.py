"""
Obligation query and management endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.agents.orchestrator import RegGraphOrchestrator
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = RegGraphOrchestrator()


@router.get("/search")
async def search_obligations(
    query: str = Query(..., description="Search query"),
    intermediary_type: Optional[str] = Query(None),
    semantic: bool = Query(True, description="Use semantic search")
):
    """
    Search obligations by keywords or semantic similarity.
    """
    try:
        results = orchestrator.search_obligations(
            query=query,
            intermediary_type=intermediary_type,
            use_semantic=semantic
        )
        
        return {
            "query": query,
            "results_count": len(results),
            "results": [
                {
                    "id": o.obligation_id,
                    "title": o.title,
                    "description": o.description[:200],
                    "status": o.status,
                    "severity": o.severity,
                    "deadline": o.deadline,
                    "responsible_party": o.responsible_party
                }
                for o in results[:20]  # Limit results
            ]
        }
        
    except Exception as e:
        logger.error(f"Error searching obligations: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{obligation_id}")
async def get_obligation_details(obligation_id: str):
    """Get detailed information about a specific obligation."""
    try:
        details = orchestrator.get_obligation_details(obligation_id)
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
        
        obl = details['obligation']
        
        return {
            "obligation_id": obligation_id,
            "title": obl.title,
            "description": obl.description,
            "circular_id": obl.circular_id,
            "clause_reference": obl.clause_reference,
            "responsible_party": obl.responsible_party,
            "required_action": obl.required_action,
            "deadline": obl.deadline,
            "deadline_type": obl.deadline_type,
            "status": obl.status,
            "severity": obl.severity,
            "evidence_status": obl.evidence_status,
            "evidence_requirements": obl.evidence_requirements,
            "intermediary_types": obl.intermediary_types,
            "dependencies": {
                "direct_dependencies": details['direct_dependencies'],
                "direct_dependents": details['direct_dependents'],
                "transitive_dependents_count": len(details['transitive_dependents'])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving obligation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_obligations(
    intermediary_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """List all obligations with optional filtering."""
    try:
        all_obligations = orchestrator.graph.get_all_obligations()
        
        # Apply filters
        if intermediary_type:
            all_obligations = [
                o for o in all_obligations
                if intermediary_type in o.intermediary_types
            ]
        
        if severity:
            all_obligations = [
                o for o in all_obligations
                if o.severity == severity
            ]
        
        if status:
            all_obligations = [
                o for o in all_obligations
                if o.status == status
            ]
        
        total = len(all_obligations)
        paginated = all_obligations[skip:skip + limit]
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "count": len(paginated),
            "obligations": [
                {
                    "id": o.obligation_id,
                    "title": o.title,
                    "status": o.status,
                    "severity": o.severity,
                    "intermediary_types": o.intermediary_types,
                    "deadline": o.deadline
                }
                for o in paginated
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing obligations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{obligation_id}/impact")
async def get_obligation_impact(obligation_id: str):
    """Get impact analysis for an obligation."""
    try:
        details = orchestrator.get_obligation_details(obligation_id)
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
        
        return {
            "obligation_id": obligation_id,
            "direct_dependents": details['direct_dependents'],
            "transitive_dependents": details['transitive_dependents'],
            "total_affected": len(details['transitive_dependents']),
            "impact_severity": "high" if len(details['transitive_dependents']) > 5 else "medium" if len(details['transitive_dependents']) > 0 else "low"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving impact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
