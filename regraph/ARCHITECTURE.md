# RegGraph - Architecture & Implementation Guide

## 📐 System Architecture

### High-Level Data Flow

```
User uploads circular (PDF/text)
        ↓
        └─→ FastAPI Endpoint (POST /api/v1/circulars/upload)
            ↓
            └─→ RegGraphOrchestrator.process_circular()
                ├─→ ObligationExtractionAgent.extract_obligations()
                │   ├─ Chunk circular by clauses
                │   ├─ Call Claude LLM for each chunk
                │   ├─ Extract obligation structured data
                │   └─ Identify relationships between obligations
                │
                ├─→ SemanticDiffAgent.diff_obligations()
                │   ├─ Prepare obligation summaries
                │   ├─ Call Claude for semantic comparison
                │   └─ Classify: new/modified/superseded
                │
                ├─→ ObligationGraph.add_obligations()
                │   ├─ Add nodes to NetworkX graph
                │   ├─ Add edges for relationships
                │   └─ Update obligation map
                │
                ├─→ ImpactPropagationEngine.propagate_impact()
                │   ├─ Graph traversal (BFS)
                │   ├─ Identify transitively affected
                │   └─ Map to workflows
                │
                ├─→ ComplianceMappingAgent.map_obligations_to_intermediary()
                │   ├─ Filter by intermediary type
                │   ├─ Check applicability conditions
                │   └─ Generate action items
                │
                ├─→ Generate ChangeImpactReport
                │   ├─ Summarize changes
                │   ├─ Assess risk level
                │   └─ Prioritize actions
                │
                └─→ Persist state
                    ├─ Save obligation_graph.pkl
                    ├─ Save FAISS index
                    └─ Return results
```

## 🔧 Core Components

### 1. Obligation Extraction Agent

**File**: `backend/app/agents/extraction_agent.py`

**Purpose**: Parse regulatory text into structured obligations

**Key Methods**:
- `extract_obligations()`: Main entry point
- `_chunk_circular()`: Split text intelligently
- `_extract_from_chunk()`: Use Claude to parse chunk
- `_link_obligation_relationships()`: Identify connections

**Claude Prompts Used**:
1. **Extraction Prompt**: Structured obligation parsing
   - Instructs Claude to extract specific fields
   - Provides JSON schema
   - Handles edge cases

2. **Relationship Prompt**: Link related obligations
   - Identifies dependencies
   - Spots cross-references
   - Detects conflicts

**Output**: List of `Obligation` objects

### 2. Semantic Diff Agent

**File**: `backend/app/agents/diff_agent.py`

**Purpose**: Compare new against existing obligations meaningfully

**Key Insight**: Doesn't use simple text matching
- "Quarterly margin report" vs "Submit margin utilization report every 3 months" = SAME
- Handles paraphrasing and reformatting
- Detects "amends clause X" patterns

**Key Methods**:
- `diff_obligations()`: Main diff pipeline
- `_semantic_diff()`: Claude-powered comparison
- `identify_amendments()`: Extract amendment references

**Claude Prompts Used**:
1. **Diff Prompt**: Semantic obligation comparison
   - Compares meaning, not text
   - Returns diff classification
   - Identifies changes

**Output**: `DiffResult` with new/modified/superseded lists

### 3. Obligation Graph

**File**: `backend/app/graph/obligation_graph.py`

**Purpose**: Maintain obligation dependency graph using NetworkX

**Data Structure**:
- **Nodes**: Obligation objects
- **Edges**: Relationships (depends_on, supersedes, cross_reference)
- **Attributes**: Status, evidence, severity, timestamps

**Key Methods**:
- `add_obligation()`: Insert node
- `add_edge()`: Create relationship
- `get_transitive_dependents()`: BFS traversal
- `mark_superseded()`: Update status
- `get_evidence_gaps()`: Group by status
- `save() / load()`: Persistence

**Persistence**: Pickled NetworkX graph

### 4. Impact Propagation Engine

**File**: `backend/app/agents/impact_propagation.py`

**Purpose**: Calculate ripple effects through obligation graph

**Algorithm**:
```
for each changed_obligation:
    direct = get immediate dependents
    transitive = BFS traverse all descendants
    affected_workflows = extract keywords from all affected
    effort = categorize by description keywords
```

**Key Methods**:
- `propagate_impact()`: Main propagation
- `get_impact_timeline()`: Group by deadlines
- `calculate_implementation_effort()`: Estimate effort
- `get_critical_dependencies()`: Highlight critical path

**Output**: Detailed impact analysis

### 5. Compliance Mapping Agent

**File**: `backend/app/agents/mapping_agent.py`

**Purpose**: Map obligations to intermediary-specific compliance

**Applicability Logic**:
1. Filter by `intermediary_types` field
2. Use Claude to refine based on:
   - Intermediary profile (activities, AUM, client count)
   - Custom conditions
   - Exemptions

3. Generate action items by responsible party

**Intermediary Profiles**:
- **Stockbroker**: Trading, settlement, margin management
- **RTA**: Shareholder management, dividend processing
- **Investment Adviser**: Portfolio advice, client communication

**Key Methods**:
- `map_obligations_to_intermediary()`: Main mapping
- `_refine_applicability()`: Claude-based filtering
- `_generate_action_items()`: Create action list

**Output**: `ComplianceMapResult` with mapped obligations

### 6. FAISS Retrieval Layer

**File**: `backend/app/retrieval/faiss_search.py`

**Purpose**: Semantic search over obligation corpus

**Process**:
1. Generate embeddings for each obligation description
2. Index embeddings with FAISS
3. On search: embed query, find nearest neighbors

**Fallback**: If FAISS unavailable, uses keyword matching

**Key Methods**:
- `add_clause_embedding()`: Index obligation
- `search_similar()`: Find related obligations
- `_get_embedding()`: Generate embedding

**Index**: Persisted to `data/faiss_index`

### 7. Orchestrator

**File**: `backend/app/agents/orchestrator.py`

**Purpose**: Coordinate all agents through pipeline

**Pipeline Steps**:
1. Extract obligations
2. Perform semantic diff
3. Add to graph
4. Propagate impact
5. Map to intermediaries
6. Generate report
7. Persist state

**Key Methods**:
- `process_circular()`: Main orchestration
- `_generate_impact_report()`: Summarize changes
- `get_compliance_dashboard()`: Intermediary view

## 🌐 API Layer

### FastAPI Endpoints

**Files**: `backend/app/api/`

#### Circular Management (`circulars.py`)
- `POST /api/v1/circulars/upload`: Process new circular
- `GET /api/v1/circulars/{circular_id}`: Get circular details
- `GET /api/v1/circulars`: List processed circulars

#### Obligation Queries (`obligations.py`)
- `GET /api/v1/obligations/search`: Semantic search
- `GET /api/v1/obligations/{obligation_id}`: Get details
- `GET /api/v1/obligations`: List with filters
- `GET /api/v1/obligations/{id}/impact`: Impact analysis

#### Compliance (`compliance.py`)
- `GET /api/v1/compliance/dashboard/{type}`: Dashboard
- `GET /api/v1/compliance/evidence-gaps/{type}`: Gap analysis
- `GET /api/v1/compliance/mapping/{type}`: Obligation mapping

#### Graph Analysis (`graph.py`)
- `GET /api/v1/graph/statistics`: Overall stats
- `GET /api/v1/graph/dependencies/{id}`: Dependency info
- `GET /api/v1/graph/impact/{id}`: Impact propagation
- `GET /api/v1/graph/export/json`: Export full graph

## 📊 Frontend Dashboard

**File**: `frontend/dashboard.py` (Streamlit)

**Features**:
- **Dashboard Overview**: Key metrics, evidence status
- **Search**: Semantic obligation search
- **Compliance Mapping**: Intermediary-specific view
- **Graph Analysis**: Dependency visualization
- **Evidence Gaps**: Color-coded status (green/yellow/red)
- **Impact Analysis**: Propagation visualization
- **Upload**: Circular ingestion interface

**Data Flow**:
```
User interaction → API call → Get JSON → Streamlit visualization
```

## 💾 Data Structures

### Obligation JSON Schema

```json
{
  "obligation_id": "SEBI_2024_001_obl_1",
  "circular_id": "SEBI_2024_001",
  "clause_reference": "Section 2.1",
  "title": "Quarterly Margin Report",
  "description": "Submit quarterly margin utilization report",
  "responsible_party": "Compliance Officer",
  "required_action": "Submit report to exchange",
  "deadline": "Quarterly",
  "deadline_type": "recurring",
  "intermediary_types": ["stockbroker"],
  "conditions": {},
  "evidence_requirements": ["Exchange receipt"],
  "evidence_status": "yellow",
  "status": "active",
  "version": 1,
  "keywords": ["margin", "reporting", "quarterly"],
  "severity": "high",
  "related_obligations": [],
  "supersedes": null,
  "superseded_by": null
}
```

### Graph Edge Schema

```python
{
  "source": "obligation_id_1",
  "target": "obligation_id_2",
  "edge_type": "depends_on",  # or "supersedes", "cross_reference"
  "weight": 1.0
}
```

## 🔄 Processing Pipeline Details

### Step 1: Chunking

**Goal**: Break circular into manageable pieces while preserving clause integrity

**Algorithm**:
- Split by periods (simple version)
- Respect clause boundaries (production version)
- Default chunk size: 3000 characters

**Reason**: Stay within LLM context limits

### Step 2: Extraction

**Claude Instructions** (simplified):
```
Extract from this circular excerpt:
1. Specific action required
2. Who is responsible
3. Deadline or frequency
4. Who must comply
5. Evidence needed

Return as JSON array of obligations.
```

**Token Budget**: ~4000 tokens per chunk

### Step 3: Relationship Linking

**Claude Instructions**:
```
Which of these obligations are related?
- INDEPENDENT
- DEPENDENT
- CROSS_REFERENCE

Return mapping: id -> [related_ids]
```

### Step 4: Semantic Diff

**Claude Comparison Logic**:
```
For each new obligation:
- Find best-matching existing obligation
- If similarity > threshold:
  - Check if deadline changed → MODIFY
  - Check if conditions relaxed → MODIFY
  - Check if explicitly "replaces" → SUPERSEDE
- If no match:
  - NEW
```

### Step 5: Impact Propagation

**Graph Traversal** (BFS):
```
queue = [changed_obligation_id]
visited = {}

while queue not empty:
    current = queue.pop()
    for dependent in graph.get_dependents(current):
        if dependent not in visited:
            affected.add(dependent)
            queue.push(dependent)
```

### Step 6: Compliance Mapping

**Claude Filtering**:
```
This intermediary is: stockbroker
Activities: trading, settlement, margin management

Does each obligation apply?
- Explicit mention of "stockbroker" → YES
- Relevant to activities → YES
- Meets conditions (AUM, clients) → YES
- Has exemption → NO
```

## 🚀 Deployment Considerations

### Docker (Future)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Scaling

1. **LLM Calls**: Cache extraction results, use async calls
2. **Graph Size**: Migrate to Neo4j for >50k obligations
3. **Search**: Dedicated FAISS or Pinecone cluster
4. **API**: Load balancer + multiple FastAPI workers

### Security

1. Add JWT authentication
2. Rate limiting on upload endpoint
3. Input sanitization before LLM calls
4. API key rotation for Anthropic

## 🧪 Testing Strategy

### Unit Tests
- Test individual agent methods
- Mock Claude API calls
- Verify graph operations

### Integration Tests
- Full circular processing
- Diff accuracy
- Impact propagation correctness

### End-to-End
- Demo with sample circular
- API endpoint validation
- Dashboard functionality

---

**Last Updated**: July 2024
**Version**: 0.1.0
