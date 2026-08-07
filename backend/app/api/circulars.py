"""
Circular management endpoints.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, List
from pydantic import BaseModel
from app.agents.orchestrator import RegGraphOrchestrator
from app.models.obligation import CircularMetadata, ChangeImpactReport
from app.llm_errors import LLMError
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Global orchestrator instance
orchestrator = RegGraphOrchestrator()


class CircularUploadRequest(BaseModel):
    """Request model for circular upload."""
    circular_id: str
    title: str
    document_text: str
    intermediary_types: Optional[List[str]] = None


class CircularResponse(BaseModel):
    """Response model for circular processing."""
    circular_id: str
    status: str
    extracted_obligations_count: int
    new_obligations_count: int
    modified_obligations_count: int
    superseded_obligations_count: int
    impact_score: float
    risk_level: str
    # Lets the UI distinguish "found 0 obligations" from "0 because the LLM failed"
    chunks_total: int = 0
    chunks_failed: int = 0
    llm_error: Optional[str] = None


@router.post("/upload")
async def upload_circular(request: CircularUploadRequest) -> CircularResponse:
    """
    Upload and process a new regulatory circular.
    
    Triggers the full pipeline:
    1. Extract obligations
    2. Semantic diff against existing graph
    3. Propagate impact
    4. Generate impact report
    """
    try:
        logger.info(f"Processing circular: {request.circular_id}")
        
        result = orchestrator.process_circular(
            circular_text=request.document_text,
            circular_id=request.circular_id,
            circular_title=request.title,
            intermediary_types=request.intermediary_types
        )
        
        chunks_failed = result.get('chunks_failed', 0)

        return CircularResponse(
            circular_id=request.circular_id,
            status="processed" if not chunks_failed else "processed_with_errors",
            extracted_obligations_count=len(result['extracted_obligations']),
            new_obligations_count=result['diff_result'].new_obligations_count if hasattr(result['diff_result'], 'new_obligations_count') else len(result['diff_result'].new_obligations),
            modified_obligations_count=len(result['diff_result'].modified_obligations),
            superseded_obligations_count=len(result['diff_result'].superseded_obligations),
            impact_score=result['impact_report'].overall_impact_score,
            risk_level=result['impact_report'].risk_level,
            chunks_total=result.get('chunks_total', 0),
            chunks_failed=chunks_failed,
            llm_error=result.get('llm_error'),
        )

    except LLMError as e:
        # The model is unreachable/misconfigured — report it as such rather than
        # returning a "successful" run with zero obligations.
        logger.error(f"LLM failure processing circular: {e}")
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")
    except Exception as e:
        logger.error(f"Error processing circular: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-file")
async def upload_circular_file(
    file: UploadFile = File(...),
    circular_id: str = Form(...),
    title: str = Form(...),
    intermediary_types: Optional[str] = Form(None)
) -> CircularResponse:
    """Upload a circular as a file (PDF/TXT). PDFs are parsed with pdfplumber."""
    try:
        content = await file.read()
        filename = file.filename or ""

        if filename.lower().endswith(".pdf"):
            # Use pdfplumber for PDF extraction
            import pdfplumber, io
            document_text = ""
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            document_text += t + "\n"
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not read PDF '{filename}': {e}. "
                           "If it is password-protected, remove the protection and retry.",
                )
            if not document_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"No text layer found in '{filename}'. This looks like a scanned "
                           "image PDF — OCR it first, or paste the text manually.",
                )
        else:
            # Try UTF-8 then fall back to latin-1 for plain text
            try:
                document_text = content.decode("utf-8")
            except UnicodeDecodeError:
                document_text = content.decode("latin-1")

        intermediary_list = None
        if intermediary_types:
            intermediary_list = [t.strip() for t in intermediary_types.split(",")]

        request = CircularUploadRequest(
            circular_id=circular_id,
            title=title,
            document_text=document_text,
            intermediary_types=intermediary_list
        )

        return await upload_circular(request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{circular_id}")
async def get_circular_details(circular_id: str):
    """Get details about a processed circular."""
    try:
        obligations = orchestrator.graph.get_by_circular(circular_id)
        
        if not obligations:
            raise HTTPException(status_code=404, detail=f"Circular {circular_id} not found")
        
        return {
            "circular_id": circular_id,
            "obligations_count": len(obligations),
            "obligations": [
                {
                    "id": o.obligation_id,
                    "title": o.title,
                    "status": o.status,
                    "severity": o.severity
                }
                for o in obligations
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving circular: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_circulars():
    """List all processed circulars."""
    all_obligations = orchestrator.graph.get_all_obligations()
    circular_ids = set(o.circular_id for o in all_obligations)
    
    return {
        "count": len(circular_ids),
        "circulars": sorted(list(circular_ids))
    }
