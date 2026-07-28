"""
Obligation data models for RegGraph system.
"""
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


# ─── Evidence checklist ──────────────────────────────────────────────────────

class ChecklistItem(BaseModel):
    """Single evidence checklist item with completion state."""
    item_id: str
    label: str
    completed: bool = False
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


# ─── Compliance Action (Tier 1A) ─────────────────────────────────────────────

class ComplianceAction(BaseModel):
    """
    Structured, executable compliance task derived from an obligation.
    Transforms the flat required_action string into an assignable work item.
    """
    action_id: str                          # e.g. ACT-00032
    obligation_id: str                      # source obligation
    circular_id: str

    # Assignment
    department: str                         # Risk Management / Compliance / Trading Ops / Legal
    owner: str                              # responsible role
    priority: str = "medium"               # critical / high / medium / low  (derived from severity + deadline)

    # Scheduling
    due_date: Optional[str] = None          # ISO date or human string
    days_remaining: Optional[int] = None    # computed from deadline
    overdue: bool = False

    # Task detail
    title: str
    description: str
    steps: List[str] = Field(default_factory=list)  # numbered SOP steps
    evidence_required: List[str] = Field(default_factory=list)

    # Links
    dependencies: List[str] = Field(default_factory=list)  # linked obligation/version IDs

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "open"                   # open / in_progress / completed / overdue


# ─── Regulatory evolution (Tier 3B) ──────────────────────────────────────────

class ObligationVersion(BaseModel):
    """One entry in the version chain for an obligation."""
    circular_id: str
    circular_title: str
    version: int
    timestamp: datetime
    changes: List[str] = Field(default_factory=list)   # what changed vs previous
    clause_reference: str = ""
    status: str = "active"


class ObligationStatus(str, Enum):
    """Status of an obligation in the compliance graph."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    MODIFIED = "modified"
    ARCHIVED = "archived"


class EvidenceStatus(str, Enum):
    """Evidence gap status for an obligation."""
    COMPLETE = "green"      # All evidence collected
    PARTIAL = "yellow"      # Some evidence collected
    MISSING = "red"         # No evidence collected


class Obligation(BaseModel):
    """
    Represents a single regulatory obligation extracted from a circular.
    This is a node in the obligation graph.
    """
    obligation_id: str = Field(..., description="Unique identifier for the obligation")
    circular_id: str = Field(..., description="Source circular ID")
    clause_reference: str = Field(..., description="Original clause reference (e.g., 'Section 2.1.1')")
    
    # Core obligation details
    title: str = Field(..., description="Brief title of the obligation")
    description: str = Field(..., description="Detailed description of what must be done")
    responsible_party: str = Field(..., description="Who is responsible (e.g., 'Compliance Officer', 'Risk Committee')")
    required_action: str = Field(..., description="Specific action required")
    
    # Deadline and frequency
    deadline: Optional[str] = Field(None, description="Deadline or frequency (e.g., 'Quarterly', '2024-03-31')")
    deadline_type: Optional[str] = Field(None, description="Type of deadline: fixed, recurring, relative")
    
    # Intermediary applicability
    intermediary_types: List[str] = Field(
        default=["stockbroker", "rta", "investment_adviser"],
        description="Which intermediary types this applies to"
    )
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions for applicability (e.g., AUM threshold)"
    )
    
    # Evidence and audit trail
    evidence_requirements: List[str] = Field(
        default_factory=list,
        description="What evidence is needed to demonstrate compliance"
    )
    evidence_status: EvidenceStatus = Field(
        default=EvidenceStatus.MISSING,
        description="Current evidence collection status"
    )
    evidence_notes: Optional[str] = Field(None, description="Notes on evidence status")
    
    # Status and versioning
    status: ObligationStatus = Field(default=ObligationStatus.ACTIVE)
    version: int = Field(default=1, description="Version number of this obligation")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relations (for graph connections)
    related_obligations: List[str] = Field(
        default_factory=list,
        description="IDs of related obligations"
    )
    supersedes: Optional[List[str]] = Field(
        None, description="Obligation IDs that this supersedes"
    )
    superseded_by: Optional[List[str]] = Field(
        None, description="Obligation IDs that supersede this"
    )
    
    # Additional metadata
    keywords: List[str] = Field(default_factory=list, description="Searchable keywords")
    severity: str = Field(default="medium", description="Compliance severity: high, medium, low")

    # ── Tier 1B: Risk score ──────────────────────────────────────────────────
    risk_score: float = Field(default=0.0, description="0-100 composite risk score")
    risk_label: str = Field(default="Low", description="Low / Medium / High")

    # ── Tier 3C: Explainability ──────────────────────────────────────────────
    extraction_rationale: Optional[str] = Field(None, description="Why this obligation was extracted")
    confidence_score: float = Field(default=0.8, description="Extraction confidence 0-1")
    mandatory_keywords: List[str] = Field(default_factory=list, description="Keywords that triggered extraction (shall, must, required)")

    # ── Tier 3D: Evidence checklist ──────────────────────────────────────────
    evidence_checklist: List[ChecklistItem] = Field(default_factory=list)

    # ── Tier 3B: Regulatory evolution ────────────────────────────────────────
    version_history: List["ObligationVersion"] = Field(default_factory=list)


class CircularMetadata(BaseModel):
    """Metadata about a regulatory circular."""
    circular_id: str
    title: str
    issuer: str = Field(default="SEBI", description="Regulatory issuer")
    issue_date: datetime
    effective_date: Optional[datetime] = None
    last_amended: Optional[datetime] = None
    circular_url: Optional[str] = None
    document_text: str = Field(..., description="Full text of the circular")
    summary: str = Field(..., description="AI-generated summary")
    
    # Amendment tracking
    amends: Optional[str] = Field(None, description="ID of circular being amended")
    amendment_type: Optional[str] = Field(None, description="supersession, modification, clarification")


class DiffResult(BaseModel):
    """Result of semantic diff between new and existing obligations."""
    new_obligations: List[Obligation] = Field(default_factory=list)
    modified_obligations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {old_id, new_obligation, changes}"
    )
    superseded_obligations: List[str] = Field(
        default_factory=list,
        description="Obligation IDs that are now superseded"
    )
    impact_score: float = Field(0.0, description="Overall impact score 0-1")


class ImpactPropagationResult(BaseModel):
    """Result of impact propagation through the obligation graph."""
    directly_affected: List[str] = Field(default_factory=list)
    indirectly_affected: List[str] = Field(default_factory=list)
    affected_workflows: List[str] = Field(default_factory=list)
    dependency_chain: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapping of obligation_id -> list of dependent obligation_ids"
    )
    total_affected_count: int = 0


class ComplianceMapResult(BaseModel):
    """Mapping of obligations to intermediary compliance profile."""
    intermediary_type: str
    applicable_obligations: List[Obligation]
    not_applicable_obligations: List[str] = Field(default_factory=list)
    critical_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    action_items: List[Dict[str, Any]] = Field(default_factory=list)


class ChangeImpactReport(BaseModel):
    """Auto-generated report for a new circular's impact."""
    circular_id: str
    report_generated_at: datetime = Field(default_factory=datetime.now)
    
    # Impact summary
    new_obligations_count: int = 0
    modified_obligations_count: int = 0
    superseded_obligations_count: int = 0
    
    # Affected areas
    affected_workflows: List[str] = Field(default_factory=list)
    affected_teams: List[str] = Field(default_factory=list)
    
    # Risk assessment
    overall_impact_score: float = Field(0.0, description="0-1 scale")
    risk_level: str = Field("medium", description="low, medium, high, critical")
    
    # Recommendations
    priority_actions: List[Dict[str, Any]] = Field(default_factory=list)
    implementation_timeline: Dict[str, str] = Field(default_factory=dict)
