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


@router.get("/urgency")
async def get_urgency_queue(
    intermediary_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Obligations sorted by composite risk score (highest = most urgent)."""
    queue = orchestrator.get_urgency_queue(intermediary_type)
    return {"total": len(queue), "intermediary_type": intermediary_type, "queue": queue[:limit]}


@router.get("/{obligation_id}/sop")
async def get_obligation_sop(
    obligation_id: str,
    use_llm: bool = Query(False),
):
    """Generate a numbered SOP for a specific obligation."""
    obl = orchestrator.graph.get_obligation(obligation_id)
    if not obl:
        raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
    from app.agents.sop_agent import generate_sop
    steps = generate_sop(obl, use_llm=use_llm)
    return {"obligation_id": obligation_id, "title": obl.title,
            "clause_reference": obl.clause_reference, "sop_steps": steps,
            "step_count": len(steps), "generated_by": "llm" if use_llm else "template"}


@router.get("/{obligation_id}/explainability")
async def get_obligation_explainability(obligation_id: str):
    """Why was this obligation extracted?"""
    obl = orchestrator.graph.get_obligation(obligation_id)
    if not obl:
        raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
    return {"obligation_id": obligation_id, "title": obl.title,
            "clause_reference": obl.clause_reference,
            "extraction_rationale": obl.extraction_rationale or "Extracted as a compliance requirement.",
            "confidence_score": obl.confidence_score,
            "mandatory_keywords": obl.mandatory_keywords,
            "severity": obl.severity, "intermediary_types": obl.intermediary_types}


@router.get("/{obligation_id}/timeline")
async def get_obligation_timeline(obligation_id: str):
    """Regulatory evolution / version history for an obligation."""
    obl = orchestrator.graph.get_obligation(obligation_id)
    if not obl:
        raise HTTPException(status_code=404, detail=f"Obligation {obligation_id} not found")
    history = obl.version_history if obl.version_history else []
    current = {"version": obl.version, "circular_id": obl.circular_id,
               "clause_reference": obl.clause_reference, "status": obl.status.value,
               "changes": ["Initial extraction"] if obl.version == 1 else ["Updated"],
               "timestamp": obl.updated_at.isoformat() if obl.updated_at else None}
    timeline = [v.model_dump() if hasattr(v, "model_dump") else v for v in history]
    if not any(e.get("version") == obl.version for e in timeline):
        timeline.append(current)
    return {"obligation_id": obligation_id, "title": obl.title,
            "current_version": obl.version, "current_status": obl.status.value,
            "superseded_by": obl.superseded_by or [], "supersedes": obl.supersedes or [],
            "version_timeline": sorted(timeline, key=lambda e: e.get("version", 0))}


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
