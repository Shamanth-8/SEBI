# RegGraph: Regulatory Obligation Dependency Graph

RegGraph transforms regulatory compliance from document-based to dependency-based by treating SEBI obligations as an interconnected graph, automatically detecting impact propagation when new circulars are issued.

**Powered by**: OpenRouter API (with OpenAI SDK) + Claude LLM + NetworkX + Streamlit

## 🎯 Key Features

- **🤖 Agentic Processing**: Multi-agent orchestration for extraction, diffing, impact analysis, and compliance mapping
- **Obligation Graph Construction**: Parse regulatory circulars into obligation nodes with semantic relationships
- **Semantic Diff Agent**: Compare new obligations against existing graph using meaning-based matching
- **Impact Propagation**: Automatically identify downstream obligations affected by changes
- **Compliance Mapping**: Map obligations to specific intermediary profiles (stockbroker, RTA, adviser)
- **Evidence Gap Coloring**: Green (complete) / Yellow (partial) / Red (missing) status visualization
- **Interactive Dashboard**: Real-time compliance monitoring and evidence tracking
- **Multi-Provider LLM Support**: Works with OpenRouter (default) or direct Anthropic API
- **RESTful API**: Complete API for integration and automation

## 📋 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     RegGraph System                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DASHBOARD LAYER (User Interface)                              │
│  ├─ Streamlit Frontend (http://localhost:8501)                 │
│  └─ 8 Interactive Views                                        │
│                                                                 │
│  API LAYER (RESTful Integration)                               │
│  ├─ 30+ FastAPI Endpoints                                      │
│  ├─ Circular Management, Obligation Queries                    │
│  ├─ Compliance Mapping, Graph Analysis                         │
│  └─ OpenAPI Documentation (http://localhost:8000/docs)         │
│                                                                 │
│  ORCHESTRATION LAYER (Agentic Processing)                      │
│  ├─ Orchestrator (7-step pipeline)                             │
│  ├─ Extraction Agent (Claude LLM)                              │
│  ├─ Diff Agent (Semantic comparison)                           │
│  ├─ Impact Propagation Engine (Graph traversal)                │
│  └─ Compliance Mapping Agent (Intermediary filtering)          │
│                                                                 │
│  LLM LAYER (Language Model Interface)                          │
│  ├─ Anthropic Adapter (abstraction layer)                      │
│  ├─ OpenRouter API (default, cost-effective)                   │
│  └─ Optional: Direct Anthropic API                             │
│                                                                 │
│  DATA LAYER (Persistence & Search)                             │
│  ├─ NetworkX Graph (obligation dependencies)                   │
│  ├─ FAISS Index (semantic search embeddings)                   │
│  └─ Pickle Storage (persistence)                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### How It Works: End-to-End Flow

```
1. USER UPLOADS CIRCULAR
   ↓
2. EXTRACTION AGENT
   - Chunks circular into 500-word sections
   - Claude LLM extracts obligations clause-by-clause
   - Creates obligation nodes with metadata
   ↓
3. DIFF AGENT
   - Compares new obligations against existing 5000+ obligations
   - Semantic matching (not text-based)
   - Classifies: NEW, MODIFIED, SUPERSEDED
   ↓
4. GRAPH INTEGRATION
   - Adds new nodes to NetworkX graph
   - Links relationships (depends_on, supersedes, related)
   ↓
5. IMPACT PROPAGATION
   - BFS traversal of graph
   - Identifies 100-300 downstream affected obligations
   - Calculates implementation effort (high/medium/low)
   ↓
6. COMPLIANCE MAPPING
   - Filters obligations by intermediary type
   - Applies applicability conditions
   - Generates action items by responsible party
   ↓
7. REPORT & PERSIST
   - Generates change impact report
   - Updates dashboard visualizations
   - Saves graph and embeddings
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- OpenRouter API Key (recommended) OR Anthropic API Key
- pip/conda for package management

### Installation

1. **Clone and navigate to project:**
```bash
cd regraph
```

2. **Create and activate virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment (OpenRouter or Anthropic):**

**Option A: Use OpenRouter (Recommended)**
```bash
# Create .env file
cat > .env << EOF
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE
OPENROUTER_MODEL=anthropic/claude-sonnet-5
ENVIRONMENT=development
LOG_LEVEL=INFO
EOF
```

**Option B: Use Direct Anthropic API**
```bash
# Create .env file
cat > .env << EOF
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
ENVIRONMENT=development
LOG_LEVEL=INFO
EOF
```

### Verify Configuration

```bash
# Run validation script
python3 validate_openrouter.py

# Expected output:
# ✓ Configuration Check              PASS
# ✓ Adapter Initialization           PASS
# ✓ Message Interface Test           PASS
# ✓ Agent Initialization             PASS
# ✓ Provider Configuration Status    PASS
```

### Running the Application

#### Option 1: Run Both Services Together (Recommended for first-time)

```bash
# Terminal 1: Start the API & Dashboard with one command
cd regraph
python3 quickstart.py

# This will:
# 1. Initialize environment
# 2. Start FastAPI backend (port 8000)
# 3. Start Streamlit dashboard (port 8501)
# 4. Open dashboard in browser automatically
# 5. Load sample data
```

#### Option 2: Run Agentic Part (Backend Only)

If you want to use the **agentic system** (agents, orchestration, graph processing) programmatically or via API:

```bash
# Terminal 1: Start FastAPI Backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# The agentic part is now running!
# API available at: http://localhost:8000/docs
```

**What the agentic part does**:
- Receives regulatory circular documents
- Extracts obligations using Claude LLM (Extraction Agent)
- Compares with existing obligations (Diff Agent)
- Analyzes impact and finds affected obligations (Impact Propagation)
- Maps to intermediary types (Mapping Agent)
- Generates compliance reports
- Manages the obligation dependency graph

**Use the API** to interact with the agentic system:

```bash
# Upload a circular and trigger the full agentic pipeline
curl -X POST "http://localhost:8000/api/v1/circulars/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "circular_id": "SEBI/HO/MRD/CIR/2024/001",
    "title": "Updated Margin Requirements",
    "document_text": "1. Initial margin shall be 5% of contract value...",
    "intermediary_types": ["stockbroker"]
  }'

# Search obligations using semantic search
curl "http://localhost:8000/api/v1/obligations/search?query=margin+reporting"

# Get impact analysis (what obligations are affected by a change)
curl "http://localhost:8000/api/v1/graph/impact/OBL_001"

# Get compliance dashboard for specific intermediary
curl "http://localhost:8000/api/v1/compliance/dashboard/stockbroker"

# View API documentation
open http://localhost:8000/docs
```

#### Option 3: Run Dashboard Only (Frontend UI)

If the agentic backend is already running:

```bash
# Terminal 2: Start Streamlit Dashboard
cd frontend
streamlit run dashboard.py

# Dashboard available at: http://localhost:8501
```

#### Option 4: Use Programmatically

Integrate the agentic system into your Python code:

```python
from backend.app.agents.orchestrator import Orchestrator
from backend.app.graph.obligation_graph import ObligationGraph

# Create orchestrator
graph = ObligationGraph()
orchestrator = Orchestrator(graph)

# Process a circular through the full agentic pipeline
result = orchestrator.process_circular(
    circular_text="SEBI circular content...",
    circular_id="SEBI/HO/MRD/CIR/2024/001",
    title="New Margin Rules",
    intermediary_types=["stockbroker"]
)

# Result includes:
# - Extracted obligations
# - Diff analysis (new/modified/superseded)
# - Impact analysis (affected obligations)
# - Compliance mapping (action items)
print(f"Extracted: {result['extracted_count']} obligations")
print(f"Impact: {result['impact_count']} affected obligations")
```

---

## 🎯 What is the Dashboard?

The **Streamlit Dashboard** is the **user-facing interface** for the RegGraph system. It provides an interactive, real-time view of regulatory compliance obligations and their relationships.

### Dashboard Overview

```
Streamlit Dashboard (http://localhost:8501)
├─ Provides visual interface to RegGraph system
├─ Connects to FastAPI backend (agentic part)
├─ Displays obligation data and analysis
├─ Allows uploading new circulars
├─ Shows compliance status in real-time
└─ Generates compliance reports
```

### What the Dashboard Does

The dashboard **visualizes and simplifies** complex compliance data that the agentic system produces:

#### 1. **Dashboard Overview Tab** 📊
What it shows:
- Total obligations in the system
- Breakdown by severity (critical/high/medium/low)
- Evidence completion status (%)
- Recent circulars processed
- Key metrics and statistics

Behind the scenes:
- Fetches data from `/api/v1/graph/statistics`
- Aggregates obligation counts by status
- Calculates compliance readiness percentage

Use case:
- **Compliance Manager**: "What's our overall compliance status?"
- **Executive**: "How many obligations do we have?"

#### 2. **Search Obligations Tab** 🔍
What you can do:
- Search for obligations by keyword or phrase (semantic search)
- Filter by intermediary type (stockbroker/RTA/adviser)
- Expand results to see full details
- View dependencies and related obligations

Behind the scenes:
- Uses FAISS semantic search (via agentic backend)
- Queries `/api/v1/obligations/search`
- Returns top matching obligations with relevance scores

Use case:
- **Operations Officer**: "Show me all margin-related obligations"
- **Compliance Officer**: "Find KYC requirements for stockbrokers"

#### 3. **Compliance Mapping Tab** 📋
What it shows:
- All obligations applicable to selected intermediary type
- Obligations grouped by responsible party
- Priority ranking (urgent → low priority)
- Action items for each party
- Evidence requirements for each obligation

Behind the scenes:
- Calls `/api/v1/compliance/mapping/{intermediary_type}`
- Compliance Mapping Agent filters obligations
- Groups by responsible party
- Generates action items

Use case:
- **Stockbroker Compliance Team**: "What do we need to do?"
- **Cross-functional Planning**: "Who owns what?"

#### 4. **Graph Analysis Tab** 🔗
What it shows:
- Interactive dependency graph
- Obligation nodes and relationships
- Prerequisite chains
- Downstream dependencies

Behind the scenes:
- Fetches graph data from `/api/v1/graph/dependencies/{id}`
- Renders interactive visualization
- Shows what each obligation depends on

Use case:
- **Risk Manager**: "What breaks if we modify this obligation?"
- **Implementation Planning**: "What's the sequence?"

#### 5. **Evidence Gaps Tab** 🟢🟡🔴
What it shows:
- Color-coded compliance status
  - 🟢 Green: Complete evidence
  - 🟡 Yellow: Partial evidence
  - 🔴 Red: Missing critical evidence
- List of obligations by status
- Priority ranking for gaps

Behind the scenes:
- Calls `/api/v1/compliance/evidence-gaps/{intermediary_type}`
- Groups obligations by evidence_status
- Highlights highest-risk gaps

Use case:
- **Audit Preparation**: "What needs documentation?"
- **Risk Assessment**: "Where are we exposed?"

#### 6. **Impact Analysis Tab** ⚡
What it shows:
- When you modify an obligation, shows what's affected
- Effort estimates for each affected obligation
- Timeline of changes needed
- Critical workflows and dependencies

Behind the scenes:
- Calls `/api/v1/graph/impact/{obligation_id}`
- Impact Propagation Engine does BFS traversal
- Calculates ripple effects through the graph

Use case:
- **Change Management**: "If we update margin rules, what else needs changing?"
- **Project Planning**: "How much work is this change?"

#### 7. **Upload Circular Tab** 📤
What you do:
- Provide circular metadata (ID, title)
- Choose affected intermediary types
- Paste or upload circular text
- Submit for processing

Behind the scenes:
- Sends to `/api/v1/circulars/upload`
- Triggers 7-step agentic pipeline:
  1. Extraction Agent parses obligations
  2. Diff Agent compares with existing
  3. Graph Integration adds to dependency graph
  4. Impact Propagation finds affected obligations
  5. Compliance Mapping generates action items
  6. Report Generation creates summary
  7. Persistence saves all data
- Updates visible after processing (~10-15 min for large circular)

Use case:
- **Compliance Officer**: "New SEBI circular issued, process it"

#### 8. **Functions/Utilities Tab** 🔧
What it shows:
- System health and status
- Configuration details
- Model information
- API connection status
- Recent logs

Behind the scenes:
- System diagnostics
- Configuration display
- Connection testing

Use case:
- **Troubleshooting**: "Is the system working?"
- **Verification**: "Which model is active?"

### How Dashboard Connects to Agentic Part

```
User Action in Dashboard
    ↓
Dashboard sends HTTP request
    ↓
FastAPI Backend (Agentic System)
    ├─ Receives request
    ├─ Runs agents if needed
    ├─ Processes graph
    └─ Returns JSON response
    ↓
Dashboard receives data
    ↓
Dashboard renders in Streamlit UI
    ↓
User sees results
```

### Dashboard Data Flow Examples

**Scenario 1: Search for obligations**
```
User: Types "margin" in search box
    ↓
Dashboard: GET /api/v1/obligations/search?query=margin
    ↓
Backend: 
    1. FAISS semantic search
    2. Finds 15 matching obligations
    ↓
Dashboard: Displays 15 results with expand details
```

**Scenario 2: Upload new circular**
```
User: Fills form and clicks "Process"
    ↓
Dashboard: POST /api/v1/circulars/upload (with circular data)
    ↓
Backend (Agentic System):
    1. Extraction Agent → Extract 50 obligations
    2. Diff Agent → Find 15 modified
    3. Graph Integration → Update graph
    4. Impact Propagation → Find 200 affected
    5. Mapping Agent → Map to intermediaries
    6. Report Gen → Create summary
    ↓
Dashboard: Shows processing status & results
```

**Scenario 3: View compliance gaps**
```
User: Selects "Stockbroker" and clicks "Evidence Gaps"
    ↓
Dashboard: GET /api/v1/compliance/evidence-gaps/stockbroker
    ↓
Backend: 
    1. Finds all stockbroker obligations
    2. Groups by evidence_status
    3. Returns counts and details
    ↓
Dashboard: Shows:
    - 🟢 Green: 45 complete
    - 🟡 Yellow: 23 partial
    - 🔴 Red: 12 missing
```

### Key Features of the Dashboard

1. **Real-time Updates**: Reflects latest data from backend
2. **Interactive Visualizations**: Charts, graphs, expandable details
3. **Responsive Design**: Works on desktop and tablet
4. **No Code Needed**: Click-based UI (no SQL/API knowledge required)
5. **Export Capabilities**: Download reports and data
6. **Error Handling**: Clear messages if something fails
7. **Performance**: Fast response times due to indexed searches

### Why Use the Dashboard?

✅ **Easier than API**: Click instead of typing curl commands  
✅ **Visual**: See charts and graphs instead of JSON  
✅ **Interactive**: Explore data without code  
✅ **Comprehensive**: All system features in one place  
✅ **Real-time**: Updates as data changes  
✅ **Intuitive**: Self-explanatory UI  

### Technical Stack

- **Frontend**: Streamlit (Python-based web framework)
- **Backend**: FastAPI (Python async web framework)
- **Communication**: HTTP REST API
- **Data**: JSON
- **Visualization**: Plotly charts, interactive graphs
- **State Management**: Streamlit session state

---

## 🧠 Agent Components Deep Dive

### 1. Extraction Agent (`extraction_agent.py`)
**Purpose**: Parse SEBI circulars into structured obligation nodes

**How it works**:
```
INPUT: SEBI Circular (50+ pages of text)
  ↓
CHUNKING: Split into ~500-word sections (maintains clause boundaries)
  ↓
LLM EXTRACTION: For each chunk, Claude extracts:
  - Obligation title
  - Description (what needs to be done)
  - Responsible party (who does it)
  - Required action (specific steps)
  - Deadline (when, frequency)
  - Evidence requirements (proof needed)
  - Intermediary types (who it applies to)
  - Severity (critical/high/medium/low)
  ↓
RELATIONSHIP LINKING: Claude identifies:
  - Prerequisites (must do A before B)
  - Supersessions (this replaces that)
  - Related items (thematically connected)
  ↓
OUTPUT: List of 50-200 Obligation objects with metadata
```

**Agent Prompt Strategy**:
- Uses structured JSON schema for Claude output
- Provides examples to ensure consistency
- Asks Claude to identify relationships proactively
- Includes few-shot learning examples

**Result**: Typically extracts 50-200 obligations from a typical SEBI circular

### 2. Semantic Diff Agent (`diff_agent.py`)
**Purpose**: Compare new obligations against existing graph, identify changes

**How it works**:
```
INPUT: 
  - New obligations (from extraction)
  - Existing obligations (from graph, 5000+)
  
COMPARISON:
  For each new obligation:
    1. Find most similar existing obligations (semantic similarity)
    2. Ask Claude: "Is this NEW, MODIFIED, or SUPERSEDED?"
    3. Claude analyzes meaning, not just text
    
CLASSIFICATION:
  - NEW: Completely new requirement not in graph
  - MODIFIED: Similar to existing, but with changes
  - SUPERSEDED: Replaces or amends existing obligation
  
IMPACT SCORING:
  - Assign change impact value (1-10)
  - Calculate overall circular impact
  
OUTPUT: DiffResult with categorized obligations
```

**Key Feature - Semantic Matching**:
- Not just text-based comparison
- Understands synonyms and rephrasing
- Handles amendments and clarifications
- Example: "margin call requirement" = "demand for additional margin"

**Result**: 20-40% of new obligations are modifications/supersessions, rest are new

### 3. Impact Propagation Engine (`impact_propagation.py`)
**Purpose**: Traverse graph to find affected obligations

**How it works**:
```
INPUT: New/Modified obligation to analyze

ALGORITHM: Breadth-First Search (BFS) on dependency graph
  1. Start at modified obligation node
  2. Find all obligations that depend on it
  3. Find all obligations that those depend on (transitively)
  4. Build set of affected nodes
  
EFFORT CALCULATION:
  - Categorize by implementation effort
  - Estimate time to implement changes
  - Group by responsible party
  
TIMELINE GROUPING:
  - Group affected by deadline
  - Identify critical path
  - Highlight sequence dependencies
  
OUTPUT: Impact Report with:
  - 100-300 affected obligations
  - Implementation effort breakdown
  - Timeline of changes needed
  - Critical workflow paths
```

**Graph Traversal Example**:
```
If you modify "Margin Report" obligation:
  → Affects "Risk Monitoring" (depends on margin data)
    → Affects "Compliance Certification" (depends on risk)
      → Affects "Board Reporting" (depends on certification)
Total: 50 obligations in chain
```

**Result**: Typically shows 100-300 downstream effects per modification

### 4. Compliance Mapping Agent (`mapping_agent.py`)
**Purpose**: Map obligations to specific intermediary profiles

**How it works**:
```
INPUT: All extracted obligations

FOR EACH INTERMEDIARY TYPE (stockbroker/rta/adviser):
  
  APPLICABILITY CHECK:
    1. Read intermediary profile rules
    2. For each obligation:
       - Does it apply to this type?
       - Are there AUM/size conditions?
       - Are there exemptions?
    3. Claude evaluates: "Apply this to stockbrokers?"
  
  ACTION ITEM GENERATION:
    1. Convert obligation → actionable task
    2. Assign to responsible party
    3. Set priority (urgent/high/medium/low)
    4. Identify resource needs
  
  EVIDENCE MAPPING:
    1. What proof is needed?
    2. Where to get evidence?
    3. Who collects it?
  
OUTPUT: ComplianceMapResult with:
  - Filtered obligations (50-150 per type)
  - Action items by responsible party
  - Evidence requirements
  - Compliance dashboard ready
```

**Intermediary Rules**:
- **Stockbroker**: All obligations + specific trading rules
- **RTA**: Registry-specific + client communication rules
- **Investment Adviser**: Advisory-specific + discretion rules

**Result**: Customized compliance requirements per intermediary type

---

## 🤖 Agentic System Architecture

The **agentic part** is the brain of RegGraph - a sophisticated multi-agent system that automatically processes regulatory requirements.

### What is the Agentic System?

The agentic system is a **pipeline of specialized AI agents** that work together to:
1. **Extract** obligations from regulatory text using Claude LLM
2. **Compare** new requirements with existing ones (semantic diffing)
3. **Propagate** changes through the obligation dependency graph
4. **Map** requirements to specific intermediary types
5. **Generate** compliance reports and action items

### How the Agentic System Works

```
┌─────────────────────────────────────────────────────────────┐
│                  Agentic Processing Pipeline                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: Extraction Agent                                 │
│  Input: Raw regulatory circular (50+ pages)               │
│  Process: Claude LLM extracts obligations clause-by-clause│
│  Output: 50-200 structured obligations                    │
│  Time: ~3 minutes                                         │
│                                                             │
│  Step 2: Semantic Diff Agent                              │
│  Input: New obligations + 5000+ existing obligations      │
│  Process: Meaning-based comparison (not text-based)       │
│  Output: NEW / MODIFIED / SUPERSEDED classifications      │
│  Time: ~2 minutes                                         │
│                                                             │
│  Step 3: Graph Integration                                │
│  Input: Classified obligations                            │
│  Process: Add nodes to NetworkX graph, link relationships │
│  Output: Updated obligation dependency graph              │
│  Time: <1 minute                                          │
│                                                             │
│  Step 4: Impact Propagation Engine                        │
│  Input: Modified obligations                              │
│  Process: BFS traversal to find affected obligations      │
│  Output: 100-300 downstream affected obligations          │
│  Time: ~1 minute                                          │
│                                                             │
│  Step 5: Compliance Mapping Agent                         │
│  Input: All extracted obligations                         │
│  Process: Filter by intermediary type, generate actions   │
│  Output: Customized compliance requirements per type      │
│  Time: ~1 minute                                          │
│                                                             │
│  Step 6: Report Generation                                │
│  Input: Results from all agents                           │
│  Process: Summarize changes, risks, action items          │
│  Output: Comprehensive impact report                      │
│  Time: <1 minute                                          │
│                                                             │
│  Step 7: Persistence                                      │
│  Input: All results                                       │
│  Process: Save graph, update embeddings, store metadata   │
│  Output: Data ready for dashboard                         │
│  Time: <1 minute                                          │
│                                                             │
│  Total Time: 10-15 minutes per circular                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

#### 1️⃣ Extraction Agent
- **What**: Parses regulatory text into structured obligations
- **How**: Uses Claude LLM with chunking and structured prompts
- **Extracts**: Title, description, responsible party, deadline, evidence needs
- **Result**: 50-200 obligations per circular

#### 2️⃣ Semantic Diff Agent
- **What**: Determines if obligations are new, modified, or superseded
- **How**: Semantic comparison using Claude (understands meaning)
- **Handles**: Rephrasing, amendments, clarifications
- **Result**: Classified obligations with change scores

#### 3️⃣ Impact Propagation Engine
- **What**: Finds all obligations affected by changes
- **How**: Graph traversal using Breadth-First Search (BFS)
- **Traces**: Direct and transitive dependencies
- **Result**: 100-300 affected obligations with effort estimates

#### 4️⃣ Compliance Mapping Agent
- **What**: Maps obligations to specific intermediary profiles
- **How**: Evaluates applicability based on intermediary rules
- **Generates**: Action items by responsible party
- **Result**: Customized requirements for stockbroker/RTA/adviser

### Running the Agentic System

#### As a Backend Service (API)

```bash
# Terminal 1: Start the agentic backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# The agentic system is now running!
# API available at http://localhost:8000/docs
```

Then use it via API:
```bash
# Upload circular → Triggers full agentic pipeline
curl -X POST http://localhost:8000/api/v1/circulars/upload \
  -H "Content-Type: application/json" \
  -d '{
    "circular_id": "SEBI/2024/001",
    "title": "New Regulation",
    "document_text": "Regulatory content...",
    "intermediary_types": ["stockbroker"]
  }'
```

#### Via Dashboard

```bash
# Start both backend (agentic) and frontend (dashboard)
cd frontend
streamlit run dashboard.py

# Or use quickstart to start both:
python3 quickstart.py
```

Then use the "Upload Circular" tab to trigger the agentic pipeline.

#### Programmatically in Python

```python
from backend.app.agents.orchestrator import Orchestrator
from backend.app.graph.obligation_graph import ObligationGraph

# Initialize agentic system
graph = ObligationGraph()
orchestrator = Orchestrator(graph)

# Process circular through full agentic pipeline
result = orchestrator.process_circular(
    circular_text="SEBI circular content...",
    circular_id="SEBI/2024/001",
    title="Updated Rules",
    intermediary_types=["stockbroker", "rta"]
)

# Results include:
print(f"✅ Extracted {result['extracted_count']} obligations")
print(f"🔄 Found {result['modified_count']} modifications")
print(f"💥 Impact: {result['affected_count']} obligations affected")
```

### Agentic System Features

✅ **Semantic Understanding**: Understands meaning, not just keywords  
✅ **Automatic Extraction**: No manual obligation entry needed  
✅ **Intelligent Diffing**: Finds actual changes, not false positives  
✅ **Impact Analysis**: Shows ripple effects automatically  
✅ **Compliance Mapping**: Customizes requirements by intermediary type  
✅ **Graph Persistence**: Maintains complete obligation network  
✅ **Scalable**: Handles 5000+ obligations in production  

### Agent Communication Flow

```
Step 1: Extraction Agent parses circular
        ↓
        "Here are 50 new obligations"
        ↓
Step 2: Diff Agent analyzes each obligation
        ↓
        "15 are NEW, 20 are MODIFIED, 3 are SUPERSEDED"
        ↓
Step 3: Graph Integration adds them
        ↓
        "Graph now has 5,050 obligations"
        ↓
Step 4: Impact Propagation analyzes changes
        ↓
        "200 obligations downstream are affected"
        ↓
Step 5: Mapping Agent filters by type
        ↓
        "For stockbrokers: 45 apply, 200 affected"
        ↓
Step 6: Report Generation summarizes
        ↓
        "Impact score: 8.5/10 - Major change"
        ↓
Step 7: Persistence saves everything
        ↓
        "Data ready for dashboard"
```

### LLM Invocations in Agentic System

The agentic system makes efficient use of the LLM (Claude via OpenRouter):

```
Per circular processing (~50 pages):
├─ Extraction Agent:     15-20 Claude calls (~50K tokens)
├─ Diff Agent:           10-15 Claude calls (~30K tokens)
├─ Mapping Agent:        10-15 Claude calls (~20K tokens)
└─ Total:                35-50 Claude calls (~100K tokens)

Cost with OpenRouter Claude Sonnet: ~$0.30
Time: 10-15 minutes
```

---

## 📚 API Endpoints

### Circular Management
- `POST /api/v1/circulars/upload` - Upload and process new circular (triggers 7-step pipeline)
- `POST /api/v1/circulars/upload-file` - File-based upload with multipart handling
- `GET /api/v1/circulars/{circular_id}` - Get circular details and associated obligations
- `GET /api/v1/circulars` - List all processed circulars

### Obligation Queries
- `GET /api/v1/obligations/search?query=...` - Search obligations (semantic + keyword)
- `GET /api/v1/obligations/{obligation_id}` - Get obligation details with dependencies
- `GET /api/v1/obligations` - List all obligations with filters (severity, status, intermediary)
- `GET /api/v1/obligations/{obligation_id}/impact` - Impact analysis for specific obligation

### Compliance Mapping
- `GET /api/v1/compliance/dashboard/{type}` - Intermediary compliance dashboard
- `GET /api/v1/compliance/evidence-gaps/{type}` - Color-coded evidence gap analysis
- `GET /api/v1/compliance/mapping/{type}` - Obligation mapping with action items

### Graph Analysis
- `GET /api/v1/graph/statistics` - Overall graph statistics and metrics
- `GET /api/v1/graph/dependencies/{obligation_id}` - Dependency chain analysis
- `GET /api/v1/graph/impact/{obligation_id}` - Impact propagation with effort estimates
- `GET /api/v1/graph/export/json` - Full graph export for custom analysis

### Example API Calls

```bash
# Search for margin-related obligations
curl "http://localhost:8000/api/v1/obligations/search?query=margin+reporting&intermediary_type=stockbroker" | jq

# Get impact of modifying one obligation
curl "http://localhost:8000/api/v1/graph/impact/OBL_001" | jq

# Get stockbroker compliance dashboard
curl "http://localhost:8000/api/v1/compliance/dashboard/stockbroker" | jq

# Get all evidence gaps (red status)
curl "http://localhost:8000/api/v1/compliance/evidence-gaps/stockbroker?status=red" | jq

# Get full obligation graph
curl "http://localhost:8000/api/v1/graph/export/json" > graph_export.json
```

## � Dashboard Deep Dive

The Streamlit dashboard provides 8 different views for compliance monitoring and analysis:

### 1. 📈 Dashboard Overview
**What you see**:
- **Key Metrics**: Total obligations, active count, evidence completion %
- **Severity Breakdown**: Pie chart of critical/high/medium/low
- **Evidence Status**: Bar chart of complete/partial/missing
- **Recent Circulars**: List of recently processed regulations

**How it works**:
```python
API Call → GET /api/v1/graph/statistics
Extract → Dashboard metrics from response
Render → Streamlit metrics and charts
Update → Real-time via polling
```

### 2. 🔍 Search Obligations
**What you do**:
- Type in search query (e.g., "margin management")
- Select intermediary type (optional)
- See relevant obligations with expandable details

**How it works**:
```
User Input: "margin management"
  ↓
API Call: POST /api/v1/obligations/search?query=margin&intermediary=stockbroker
  ↓
Backend: Semantic search via FAISS + keyword matching
  ↓
Response: Top 10 matching obligations with scores
  ↓
Display: Expandable cards showing details
```

**Semantic Search**: Uses FAISS to find meaning-based matches, not just keyword matches

### 3. 🗺️ Compliance Mapping
**What you see**:
- Filter by intermediary type (stockbroker/RTA/adviser)
- See all applicable obligations for that type
- View action items grouped by responsible party
- Identify compliance gaps

**How it works**:
```python
User selects: "Stockbroker"
  ↓
API Call: GET /api/v1/compliance/mapping/stockbroker
  ↓
Backend: Mapping Agent filters 5000+ obligations
  ↓
Returns: 100-150 relevant obligations with:
  - Priority ranking
  - Action items
  - Responsible parties
  - Deadlines
  ↓
Dashboard: Groups and displays
```

### 4. 🔗 Graph Analysis
**What you see**:
- Interactive dependency visualization
- Choose an obligation to explore
- See what depends on it (downstream)
- See what it depends on (prerequisites)

**How it works**:
```
User selects: "Quarterly Margin Report"
  ↓
API Call: GET /api/v1/graph/dependencies/OBL_001
  ↓
Backend: 
  1. Find direct dependencies (what it needs)
  2. Find what depends on it (downstream)
  3. Build graph data
  ↓
Response: Node-link JSON format
  ↓
Dashboard: Render interactive graph
  - Drag nodes
  - Click for details
  - Zoom/pan
```

### 5. 🔴 Evidence Gaps
**What you see**:
- Color-coded status visualization
  - 🟢 Green: Complete evidence
  - 🟡 Yellow: Partial/needs verification
  - 🔴 Red: Missing critical evidence
- List of obligations by status
- Action items to close gaps

**How it works**:
```
API Call: GET /api/v1/compliance/evidence-gaps/stockbroker
  ↓
Backend: 
  1. Check evidence_status for each obligation
  2. Group by status (green/yellow/red)
  3. Identify critical gaps
  ↓
Response: Grouped obligations with evidence details
  ↓
Dashboard: Show as color-coded list + chart
```

### 6. ⚡ Impact Analysis
**What you see**:
- Choose an obligation to modify
- See all affected obligations downstream
- View implementation effort estimate
- Timeline of required changes

**How it works**:
```
User selects: "Modify margin requirements"
  ↓
API Call: GET /api/v1/graph/impact/OBL_001
  ↓
Backend: Impact Propagation Engine
  1. BFS traversal from modified obligation
  2. Find all downstream dependents
  3. Estimate effort per obligation
  4. Group by timeline
  ↓
Response: 100-300 affected obligations with:
  - Implementation effort (high/medium/low)
  - Deadline groups
  - Critical workflows
  ↓
Dashboard: Show as timeline chart + list
```

### 7. 📤 Upload Circular
**What you do**:
- Provide circular metadata
- Paste or upload circular text
- Select applicable intermediary types
- Submit for processing

**How it works**:
```
User submits form with:
- Circular ID
- Title
- Document text
- Intermediary types
  ↓
Frontend validation
  ↓
API Call: POST /api/v1/circulars/upload
  ↓
Backend: 7-step orchestration pipeline
  1. Extraction Agent → 50-200 obligations
  2. Diff Agent → Identify NEW/MODIFIED/SUPERSEDED
  3. Graph Integration → Add to dependency graph
  4. Impact Propagation → Find affected obligations
  5. Compliance Mapping → Filter by intermediary
  6. Report Generation → Summarize changes
  7. Persistence → Save graph and embeddings
  
Processing time: 5-10 minutes for 50+ page circular
  ↓
Response: Change impact report
  ↓
Dashboard: Display processing status + results
```

### 8. 📋 Functions/Utilities (System Health)
**What you see**:
- System status and configuration
- API health check
- Latest log messages
- Model information

---

## 🔄 Processing Pipeline Example

### Scenario: SEBI Issues New Margin Circular

**Input**: SEBI/HO/MRD/CIR/2024/050 - Updated margin requirements

```bash
# Via API
curl -X POST "http://localhost:8000/api/v1/circulars/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "circular_id": "SEBI/HO/MRD/CIR/2024/050",
    "title": "Updated Margin Requirements for Derivatives",
    "document_text": "1. Initial Margin shall be 5% of contract value...",
    "intermediary_types": ["stockbroker"]
  }'
```

**Backend Processing** (7 steps, ~10 minutes):

```
Step 1: EXTRACTION
  - Parse 15-page circular
  - Extract 45 new obligations:
    - Margin calculation (5 obligations)
    - Daily reporting (3 obligations)
    - Client communication (4 obligations)
    - Risk monitoring (8 obligations)
    - etc.

Step 2: DIFFING
  - Compare against 5000+ existing obligations
  - Find that 20 obligations are MODIFIED (margin requirements updated)
  - Find that 3 obligations are SUPERSEDED (old margin rules)
  - Find that 22 obligations are NEW

Step 3: GRAPH INTEGRATION
  - Add 22 new nodes to graph
  - Update 20 modified nodes
  - Mark 3 as superseded (keep for audit trail)
  - Total graph now has 5,022 obligations

Step 4: IMPACT PROPAGATION
  - Margin changes affect:
    - Risk monitoring (200 obligations) → need new risk thresholds
    - Client reporting (150 obligations) → need updated reports
    - Settlement procedures (80 obligations) → changed margin calls
    - Compliance certification (50 obligations) → annual audit scope
  - Total downstream impact: 480 obligations

Step 5: COMPLIANCE MAPPING
  - For Stockbrokers (only intermediary type):
    - 45 new obligations apply directly
    - 480 affected obligations need review
    - Generate action items:
      * Operations team: Implement new margin calc (HIGH - day 1)
      * Risk team: Update risk thresholds (MEDIUM - day 3)
      * Compliance: Update policies (HIGH - day 1)
      * Finance: Update reporting (MEDIUM - day 5)

Step 6: REPORT GENERATION
  - Summary: "45 new obligations, 20 modified, 3 superseded, 480 affected"
  - Impact score: 8.5/10 (major change)
  - Timeline: 75 obligations due within 30 days
  - Evidence gaps: 12 new evidence types needed

Step 7: PERSISTENCE
  - Save updated graph to pickle file
  - Update FAISS embeddings
  - Store circular metadata
  - Ready for dashboard
```

**Dashboard Display**:

1. User opens Dashboard → sees alert "New circular processed"
2. Compliance Mapping → shows 45 new obligations for stockbroker
3. Impact Analysis → shows 480 affected downstream obligations
4. Evidence Gaps → shows 12 new evidence requirements (RED status)
5. Search → can search "derivative margin" and find all 45 new requirements
6. Graph → can explore dependency chain from margin calculation

---

## 📊 Dashboard Features

### Dashboard Overview
- **Metrics**: Total obligations, active count, severity breakdown, evidence %
- **Evidence Status**: Color-coded chart of complete/partial/missing evidence
- **Status Distribution**: Active vs superseded vs modified obligations
- **Recent Activity**: Latest circulars and obligations

### Compliance Mapping
- **Intermediary-specific obligations**: Automatically filtered to relevant requirements
- **Action items**: Priority-ranked tasks by responsible party
- **Critical gaps**: High-severity obligations with missing evidence
- **Timeline view**: Group obligations by deadline

### Graph Analysis
- **Dependency visualization**: Interactive graph showing which obligations depend on others
- **Drill-down**: Click nodes to see details and related obligations
- **Impact propagation**: Understand ripple effects of changes
- **Network density metrics**: Overall complexity indicators

### Evidence Gaps
- **Color-coded visualization**: Green/Yellow/Red status at a glance
- **Severity filtering**: Focus on high-priority gaps
- **Evidence requirements**: See what proof is needed
- **Audit trail**: Track compliance documentation status

### Search & Filter
- **Semantic search**: Find obligations by meaning, not just keywords
- **Intermediary filter**: Show obligations for specific types
- **Severity filter**: Focus on critical/high/medium/low
- **Status filter**: Find active/superseded/modified obligations

### Upload & Processing
- **Form-based upload**: Easy metadata entry
- **Text paste or file upload**: Flexible input methods
- **Real-time status**: See processing progress
- **Results view**: Immediate access to processed obligations

## 🧠 Agent Components

### 1. Extraction Agent
- **Input**: Raw SEBI circular (50+ pages)
- **Process**: Chunks circular into 500-word sections, extracts obligations via Claude
- **Output**: 50-200 structured obligation nodes with metadata
- **Key Attributes**: Title, description, responsible party, deadline, evidence requirements, severity
- **Special Features**: Automatically identifies relationships between obligations

### 2. Semantic Diff Agent
- **Input**: New obligations + existing 5000+ obligations in graph
- **Process**: Meaning-based comparison (not text matching) using Claude
- **Output**: Classified obligations (NEW / MODIFIED / SUPERSEDED)
- **Special Features**: Handles amendments, rephrasing, and clarifications
- **Impact Scoring**: Assigns change impact values for prioritization

### 3. Impact Propagation Engine
- **Input**: Modified/new obligation in dependency graph
- **Process**: BFS traversal to find affected obligations
- **Output**: 100-300 downstream affected obligations with effort estimates
- **Special Features**: Groups by timeline, highlights critical workflows, estimates effort
- **Result**: Comprehensive understanding of ripple effects

### 4. Compliance Mapping Agent
- **Input**: All obligations, intermediary profiles (stockbroker/RTA/adviser)
- **Process**: Evaluates applicability, generates action items
- **Output**: Customized compliance requirements per intermediary type
- **Special Features**: Applies AUM conditions, identifies responsible parties, maps evidence
- **Result**: Actionable compliance requirements tailored to each entity type

## � LLM Provider Configuration

RegGraph supports **both OpenRouter and Anthropic APIs** with transparent switching:

### OpenRouter (Recommended - Default)

**Advantages**:
- ✅ Cost-effective (Claude Haiku from $0.15 per 1M tokens)
- ✅ 70+ models available (not just Claude)
- ✅ Automatic provider routing
- ✅ No vendor lock-in
- ✅ Better for experimentation and cost optimization

**Configuration** (`.env`):
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY
OPENROUTER_MODEL=anthropic/claude-sonnet-5
```

**Model Options**:
```bash
anthropic/claude-sonnet-5        # Latest, balanced (RECOMMENDED)
anthropic/claude-opus-4.8         # Most capable
anthropic/claude-haiku-latest     # Cheapest/fastest
anthropic/claude-sonnet-latest    # Always latest sonnet
anthropic/claude-opus-latest      # Always latest opus
```

### Direct Anthropic API

**Advantages**:
- ✅ Official provider
- ✅ Potentially lower latency
- ✅ Direct support from Anthropic
- ✅ Latest models immediately available

**Configuration** (`.env`):
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
```

**Model Options**:
```bash
claude-3-sonnet-20240229         # Balanced
claude-3-opus-20240229            # Most capable
claude-3-haiku-20240307          # Fast/cheap
claude-3-5-sonnet-20241022       # Latest
```

### How Provider Switching Works

```python
# No code changes needed! Just update .env:

# Option 1: Use OpenRouter
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxx

# Option 2: Use Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# All agents automatically use the configured provider
```

### Adapter Layer

The `anthropic_adapter.py` module provides abstraction:
```
Agents (unchanged code)
    ↓
Adapter (universal interface)
    ├─ If OpenRouter: Convert to OpenAI format
    └─ If Anthropic: Use directly
    ↓
LLM API
```

**Result**: Zero code changes needed to switch providers!

---

## 💾 Data Structures

## 💾 Data Structures

### Obligation Node
```python
{
  "obligation_id": "SEBI_2024_001_obl_1",
  "circular_id": "SEBI/HO/MRD/CIR/2024/001",
  "title": "Quarterly Margin Report Submission",
  "description": "Stockbrokers must submit margin utilization reports...",
  "responsible_party": "Compliance Officer",
  "required_action": "Submit margin utilization report",
  "deadline": "Within 10 days of quarter-end",
  "deadline_type": "quarterly",  # recurring/fixed/relative
  "intermediary_types": ["stockbroker"],
  "evidence_requirements": ["signed report", "audit confirmation"],
  "evidence_status": "yellow",  # green/yellow/red
  "severity": "high",  # critical/high/medium/low
  "status": "active",  # active/superseded/modified
  "keywords": ["margin", "reporting", "risk", "risk management"],
  "created_at": "2024-01-15T10:30:00Z",
  "metadata": {
    "aum_threshold": 500000000,  # ₹500 crore
    "applicability_notes": "Applies to brokers with AUM > ₹500 crore"
  }
}
```

### Graph Edges (Relationships)
```python
# Edge types in NetworkX graph:

Edge(A, B, type="depends_on")
  # A depends on B being completed first
  # Example: "Compliance Certification" depends_on "Risk Monitoring"

Edge(A, B, type="supersedes")
  # A replaces B (B is now obsolete)
  # Example: "New Margin Rules" supersedes "Old Margin Rules"

Edge(A, B, type="cross_reference")
  # A references B but not strictly dependent
  # Example: "KYC Rules" cross_references "AML Policy"

Edge(A, B, type="related")
  # A is thematically related to B
  # Example: "Daily Margin Monitoring" related "Monthly Risk Report"
```

### Circular Metadata
```python
{
  "circular_id": "SEBI/HO/MRD/CIR/2024/001",
  "title": "Master Circular - Stockbrokers",
  "issued_date": "2024-01-15",
  "effective_date": "2024-02-15",
  "intermediary_types": ["stockbroker"],
  "total_obligations": 45,
  "status": "processed",
  "extraction_timestamp": "2024-01-15T12:30:00Z",
  "amendment_to": "SEBI/HO/MRD/CIR/2023/050",  # if applicable
  "keywords": ["margin", "risk management", "reporting"]
}
```

### DiffResult (Change Analysis)
```python
{
  "circular_id": "SEBI/HO/MRD/CIR/2024/001",
  "total_new": 22,
  "total_modified": 20,
  "total_superseded": 3,
  "new_obligations": [
    {"id": "OBL_NEW_001", "title": "...", "severity": "high"}
  ],
  "modified_obligations": [
    {"id": "OBL_001", "title": "...", "change": "deadline updated"}
  ],
  "superseded_obligations": [
    {"id": "OBL_OLD_001", "title": "...", "replaced_by": "OBL_001"}
  ],
  "impact_score": 8.5,  # 1-10 scale
  "affected_count": 480  # downstream obligations affected
}
```

### ComplianceMapResult (Intermediary-specific mapping)
```python
{
  "intermediary_type": "stockbroker",
  "applicable_obligations": [
    {
      "obligation_id": "OBL_001",
      "title": "Quarterly Margin Report",
      "priority": "high",
      "action_items": [
        {
          "action": "Calculate margin utilization",
          "responsible_party": "Operations Officer",
          "deadline": "10 days after quarter-end",
          "effort": "medium"
        }
      ]
    }
  ],
  "obligations_by_responsible_party": {
    "Compliance Officer": [12 obligations],
    "Operations Officer": [8 obligations],
    "Finance Officer": [5 obligations]
  },
  "evidence_gaps": [
    {"type": "Audit Confirmation", "required_for": 15, "status": "red"}
  ],
  "compliance_readiness": 0.65  # 65% ready
}
```

## 💾 Persistence

- **Obligation Graph**: Pickled NetworkX graph at `data/obligation_graph.pkl`
- **FAISS Index**: Semantic embeddings at `data/faiss_index`
- **Metadata**: Embedded in graph nodes and obligation objects

Load existing graph:
```python
from app.graph.obligation_graph import ObligationGraph

graph = ObligationGraph()
graph.load()  # Loads from data/obligation_graph.pkl
```

## � Quick Start Guide

### 1. Setup (One-time)
```bash
# Clone repository
cd regraph

# Create environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure (choose one):
# Option A: OpenRouter (Recommended)
echo "LLM_PROVIDER=openrouter" > .env
echo "OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY" >> .env
echo "OPENROUTER_MODEL=anthropic/claude-sonnet-5" >> .env

# Option B: Anthropic
echo "LLM_PROVIDER=anthropic" > .env
echo "ANTHROPIC_API_KEY=sk-ant-YOUR_KEY" >> .env

# Verify setup
python3 validate_openrouter.py  # Should show 5/5 PASS
```

### 2. Start Services
```bash
# Terminal 1: Start API
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Start Dashboard
cd frontend
streamlit run dashboard.py

# Terminal 3: (Optional) Run demo
python3 quickstart.py
```

### 3. Use Dashboard
1. Open http://localhost:8501
2. Explore pre-loaded obligations (if any)
3. Upload a new circular
4. View results in real-time

### 4. Use API
```bash
# Search obligations
curl "http://localhost:8000/api/v1/obligations/search?query=margin"

# Get compliance dashboard
curl "http://localhost:8000/api/v1/compliance/dashboard/stockbroker" | jq

# Analyze impact
curl "http://localhost:8000/api/v1/graph/impact/OBL_001" | jq
```

---

## 📖 Common Use Cases

### Use Case 1: Monitor New Regulation
**Scenario**: SEBI issues a new circular → Need to understand impact immediately

**Steps**:
1. Paste circular in dashboard → Upload Circular view
2. System extracts obligations and diffs against existing
3. View impact in "Impact Analysis" tab
4. See affected obligations for each intermediary type
5. Export action items for each team

**Time**: 10 minutes vs 2 days manual review

### Use Case 2: Risk Assessment
**Scenario**: Want to know highest-risk compliance gaps

**Steps**:
1. Go to "Evidence Gaps" tab
2. Filter by RED status (missing evidence)
3. Sort by severity (HIGH/CRITICAL first)
4. Review list of obligations needing attention
5. Assign tasks in action items

**Benefit**: Prioritized list of actual compliance risks

### Use Case 3: Cross-Functional Planning
**Scenario**: New regulation requires coordination across teams

**Steps**:
1. Use "Compliance Mapping" view
2. Select intermediary type (stockbroker/RTA/adviser)
3. Group action items by "Responsible Party"
4. See each team's responsibilities
5. Timeline view shows when each team needs to act

**Benefit**: Clear visibility of dependencies between teams

### Use Case 4: Audit Preparation
**Scenario**: Preparing for regulatory audit on compliance status

**Steps**:
1. Export full graph via API: `/api/v1/graph/export/json`
2. Use "Evidence Gaps" view to show audit trail
3. Generate compliance dashboard reports
4. Use search to find specific obligation implementations
5. Show complete dependency chains

**Benefit**: Comprehensive audit documentation

### Use Case 5: Compliance Trend Analysis
**Scenario**: Understand how regulations are evolving over time

**Steps**:
1. Load multiple years of circulars
2. Use graph export to analyze obligation growth
3. Identify new focus areas (e.g., "cybersecurity" appears more)
4. Compare modification rates across intermediary types
5. Identify recurring themes

**Benefit**: Strategic compliance planning insights

---

## 🔍 Understanding Agent Interactions

### When User Uploads a Circular

```
Dashboard Form → API Endpoint
  ↓
Orchestrator.process_circular()
  ├─ Step 1: ExtractionAgent.extract_obligations()
  │         └─ Claude: "Parse this clause into obligations"
  │         └─ Returns: 50-200 Obligation objects
  │
  ├─ Step 2: DiffAgent.diff_obligations()
  │         └─ Claude: "Is this new, modified, or superseded?"
  │         └─ Returns: Classified obligations
  │
  ├─ Step 3: Graph.add_obligations() + Graph.link_relationships()
  │         └─ Update NetworkX graph
  │         └─ Add edges between obligations
  │
  ├─ Step 4: ImpactPropagation.propagate_impact()
  │         └─ BFS traversal of graph
  │         └─ Find affected obligations
  │         └─ Returns: 100-300 impacted nodes
  │
  ├─ Step 5: MappingAgent.map_obligations_to_intermediaries()
  │         └─ Claude: "Does this apply to stockbrokers?"
  │         └─ Returns: Filtered + mapped obligations
  │
  ├─ Step 6: Generate Impact Report
  │         └─ Summarize changes
  │         └─ Highlight critical items
  │
  └─ Step 7: Persist graph, save embeddings
           └─ Save to disk
           └─ Update FAISS index
           
Dashboard updates → Shows results in real-time
```

### Agent Communication

1. **Extraction → Diff**: "Here are new obligations, compare them"
2. **Diff → Graph**: "These are new/modified/superseded obligations"
3. **Graph → Impact**: "These obligations changed, what's affected?"
4. **Impact → Mapping**: "These are affected obligations for each intermediary"
5. **Mapping → Dashboard**: "Here are action items grouped by responsibility"

### LLM Invocations Per Circular

```
Single 50-page circular triggers:

Extraction Agent:
  - 1 call to chunk circular
  - 10-15 calls to extract obligations (1 per chunk)
  - 1 call to identify relationships
  Total: ~15-20 Claude calls (~50,000 tokens)

Diff Agent:
  - 1 call to compare new vs existing
  - ~5-10 detailed comparison calls
  Total: ~10-15 Claude calls (~30,000 tokens)

Mapping Agent:
  - 1 call per intermediary type (3 types)
  - ~2-3 calls for action item generation per type
  Total: ~10-15 Claude calls (~20,000 tokens)

Total per circular: ~35-50 Claude calls, ~100,000 tokens
Cost (with OpenRouter Claude Sonnet): ~$0.30
Time: 5-10 minutes
```

---

## 📊 Performance Characteristics

| Operation | Time | Complexity | Notes |
|-----------|------|-----------|-------|
| Extract from 50-page circular | 3-5 min | O(pages) | Mostly LLM time |
| Diff against 5000 obligations | 2-3 min | O(new × existing) | Optimized via sampling |
| Impact propagation | 1-2 min | O(V+E) | BFS on graph |
| Compliance mapping | 1-2 min | O(obligations × types) | Parallelizable |
| FAISS semantic search | <1 sec | O(log n) | Indexed search |
| Full pipeline | 10-15 min | Linear | Sequential agents |

**Optimization Tips**:
- Cache FAISS index for faster searches (done automatically)
- Batch process multiple circulars if possible
- Use cheaper model (Haiku) for proof-of-concepts
- Implement webhook notifications instead of polling

---

## 🏗️ Project Structure

```
regraph/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app entry
│       ├── config.py            # Configuration management
│       ├── anthropic_adapter.py # LLM provider abstraction
│       ├── llm_client.py        # Alternative unified client
│       │
│       ├── agents/              # Multi-agent system
│       │   ├── extraction_agent.py
│       │   ├── diff_agent.py
│       │   ├── impact_propagation.py
│       │   ├── mapping_agent.py
│       │   └── orchestrator.py
│       │
│       ├── graph/               # Graph layer
│       │   └── obligation_graph.py
│       │
│       ├── retrieval/           # Semantic search
│       │   └── faiss_search.py
│       │
│       ├── api/                 # API routes
│       │   ├── circulars.py
│       │   ├── obligations.py
│       │   ├── compliance.py
│       │   └── graph.py
│       │
│       └── models/              # Data structures
│           └── obligation.py
│
├── frontend/
│   └── dashboard.py             # Streamlit UI (8 views)
│
├── data/
│   ├── sample_circular.py       # Sample data
│   └── sebi_obligations_dataset.csv
│
├── .env                         # Configuration file
├── requirements.txt             # Python dependencies
├── validate_openrouter.py       # Validation script
├── quickstart.py                # Demo script
├── OPENROUTER_SETUP.md          # Detailed setup guide
└── README.md                    # This file
```

---

## 📚 Additional Documentation

- **[OPENROUTER_SETUP.md](OPENROUTER_SETUP.md)** - Detailed OpenRouter configuration
- **[OPENROUTER_COMPLETE_SETUP.md](OPENROUTER_COMPLETE_SETUP.md)** - Full setup summary
- **[DATASET_GUIDE.md](DATASET_GUIDE.md)** - Working with datasets
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Deep technical architecture
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Project status
- **[INDEX.md](INDEX.md)** - Complete navigation guide

---

## 🐛 Troubleshooting

### Problem: "API Key not configured"
```bash
# Check .env file exists
ls -la .env

# Check key is set
grep OPENROUTER_API_KEY .env

# If missing, add it
echo "OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY" >> .env
```

### Problem: Slow extraction
```bash
# Try faster model
OPENROUTER_MODEL=anthropic/claude-haiku-latest

# Or increase timeout
LLM_TIMEOUT=180  # from 120 seconds
```

### Problem: Memory issues with large graph
```bash
# Reduce in-memory indexes
# Or switch to Neo4j for larger scale
# See "Future Enhancements" section
```

### Problem: Validation script fails
```bash
# Check Python version (need 3.10+)
python3 --version

# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Run verbose validation
python3 -c "
import sys; sys.path.insert(0, './backend')
from app.anthropic_adapter import create_anthropic_compatible_client
from app.config import get_settings
client = create_anthropic_compatible_client(get_settings().LLM_PROVIDER)
print(f'Provider: {get_settings().LLM_PROVIDER}')
print(f'Client: {type(client).__name__}')
"
```

---

## 📞 Support

For issues or questions:
1. Check documentation files (listed above)
2. Run validation script: `python3 validate_openrouter.py`
3. Review logs: Check terminal output
4. Test API directly: Use curl commands from examples
5. Check .env configuration: Ensure API keys are set correctly

---

## 📈 Demo Scenario

**Input**: SEBI Master Circular for Stockbrokers (50+ pages)  
**Process**: 10-15 minutes for full orchestration  
**Output**:
- ✅ 200 obligations extracted
- 📊 Obligation graph with 5000+ connected nodes
- 🔴 Impact analysis showing 300 affected obligations
- 📋 Compliance mapping with action items by party
- 📈 Dashboard showing evidence gaps and risk areas

**Benefits**:
- Automated compliance understanding
- Impact visibility in minutes instead of weeks
- Prioritized action items ready for implementation
- Audit trail and documentation automatically generated

---

**Built with**: OpenRouter API • Claude LLM • FastAPI • NetworkX • FAISS • Streamlit

**Last Updated**: 2026-07-12  
**Status**: ✅ Fully Operational with OpenRouter Integration