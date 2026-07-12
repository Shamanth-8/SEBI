#!/bin/bash
# RegGraph - Quick Reference Commands

echo "
╔════════════════════════════════════════════════════════════════╗
║           RegGraph - Quick Reference Guide                    ║
║  Regulatory Obligation Dependency Graph for SEBI Compliance   ║
╚════════════════════════════════════════════════════════════════╝
"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_section() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📋 $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_command() {
    echo -e "${GREEN}$ $1${NC}"
}

print_description() {
    echo -e "${YELLOW}   $1${NC}"
}

# Setup
print_section "1. INITIAL SETUP"
print_command "chmod +x setup.sh && ./setup.sh"
print_description "Automated setup (creates venv, installs dependencies)"

echo ""
print_command "python3 -m venv venv"
print_command "source venv/bin/activate"
print_command "pip install -r requirements.txt"
print_description "Manual step-by-step setup"

# Environment
print_section "2. CONFIGURATION"
print_command "cp .env.example .env"
print_description "Create environment file"

print_command "# Edit .env with your ANTHROPIC_API_KEY"
print_description "Add Anthropic API credentials"

# Running Services
print_section "3. START SERVICES"
print_command "# Terminal 1 - Backend API"
print_description "cd backend && python -m uvicorn app.main:app --reload --port 8000"

echo ""
print_command "# Terminal 2 - Streamlit Dashboard"
print_description "cd frontend && streamlit run dashboard.py"

echo ""
print_command "# Terminal 3 - Demo (optional)"
print_description "python quickstart.py"

# API Examples
print_section "4. API EXAMPLES"

print_command "curl http://localhost:8000/health"
print_description "Check API health"

echo ""
print_command "curl http://localhost:8000/api/v1/graph/statistics"
print_description "Get graph statistics"

echo ""
print_command "curl 'http://localhost:8000/api/v1/obligations/search?query=margin'"
print_description "Search obligations (semantic)"

echo ""
print_command "curl 'http://localhost:8000/api/v1/compliance/dashboard/stockbroker'"
print_description "Get compliance dashboard for stockbroker"

echo ""
print_command "curl 'http://localhost:8000/api/v1/compliance/evidence-gaps/stockbroker'"
print_description "Get evidence gaps analysis"

# Upload Circular
print_section "5. UPLOAD A CIRCULAR"

print_command "curl -X POST http://localhost:8000/api/v1/circulars/upload \\"
print_description "  -H 'Content-Type: application/json' \\"
print_description "  -d '{"
print_description "    \"circular_id\": \"SEBI/HO/MRD/CIR/2024/001\","
print_description "    \"title\": \"Master Circular - Stockbrokers\","
print_description "    \"document_text\": \"...\","
print_description "    \"intermediary_types\": [\"stockbroker\"]"
print_description "  }'"

# Access Points
print_section "6. ACCESS POINTS"

echo -e "${GREEN}API Documentation:${NC}"
echo "  http://localhost:8000/docs"
echo "  http://localhost:8000/redoc"
echo ""
echo -e "${GREEN}API Health:${NC}"
echo "  http://localhost:8000/health"
echo ""
echo -e "${GREEN}Streamlit Dashboard:${NC}"
echo "  http://localhost:8501"
echo ""
echo -e "${GREEN}API Base URL:${NC}"
echo "  http://localhost:8000/api/v1"

# File Structure
print_section "7. KEY FILES"

echo -e "${GREEN}Backend:${NC}"
echo "  backend/app/main.py - FastAPI entry point"
echo "  backend/app/agents/orchestrator.py - Main pipeline"
echo "  backend/app/api/ - REST endpoints"
echo ""
echo -e "${GREEN}Frontend:${NC}"
echo "  frontend/dashboard.py - Streamlit dashboard"
echo ""
echo -e "${GREEN}Documentation:${NC}"
echo "  README.md - Quick start guide"
echo "  ARCHITECTURE.md - Technical details"
echo "  IMPLEMENTATION_SUMMARY.md - What's implemented"

# Documentation
print_section "8. DOCUMENTATION"

print_command "cat README.md"
print_description "User guide and quick start"

echo ""
print_command "cat ARCHITECTURE.md"
print_description "Technical architecture details"

echo ""
print_command "cat IMPLEMENTATION_SUMMARY.md"
print_description "Implementation summary and status"

# Troubleshooting
print_section "9. TROUBLESHOOTING"

echo -e "${YELLOW}Port already in use?${NC}"
print_command "lsof -i :8000"
print_description "Find process using port 8000"
print_command "kill -9 <PID>"
print_description "Kill the process"

echo ""
echo -e "${YELLOW}Missing dependencies?${NC}"
print_command "pip install -r requirements.txt --upgrade"
print_description "Reinstall all dependencies"

echo ""
echo -e "${YELLOW}ANTHROPIC_API_KEY not set?${NC}"
print_command "export ANTHROPIC_API_KEY='your-key-here'"
print_description "Set environment variable"

# Database
print_section "10. DATA & PERSISTENCE"

echo -e "${GREEN}Saved Data:${NC}"
echo "  data/obligation_graph.pkl - Persisted obligation graph"
echo "  data/faiss_index - Semantic search embeddings"
echo ""
print_command "rm data/obligation_graph.pkl"
print_description "Reset obligation graph (start fresh)"

# Development
print_section "11. DEVELOPMENT"

print_command "python quickstart.py"
print_description "Run demo with sample circular"

echo ""
print_command "python -m pytest tests/ -v"
print_description "Run test suite (when tests are added)"

echo ""
print_command "black backend/ frontend/"
print_description "Format code"

# Useful Endpoints
print_section "12. MOST USEFUL ENDPOINTS"

echo -e "${GREEN}Dashboard Overview:${NC}"
echo "  GET /api/v1/graph/statistics"
echo "  GET /api/v1/compliance/dashboard/{intermediary_type}"
echo ""
echo -e "${GREEN}Search & Query:${NC}"
echo "  GET /api/v1/obligations/search?query={term}"
echo "  GET /api/v1/obligations/{id}"
echo ""
echo -e "${GREEN}Compliance:${NC}"
echo "  GET /api/v1/compliance/evidence-gaps/{intermediary_type}"
echo "  GET /api/v1/compliance/mapping/{intermediary_type}"
echo ""
echo -e "${GREEN}Impact Analysis:${NC}"
echo "  GET /api/v1/graph/dependencies/{obligation_id}"
echo "  GET /api/v1/graph/impact/{obligation_id}"

# Support
print_section "NEXT STEPS"

echo ""
echo -e "${GREEN}1. Run Setup:${NC}"
echo "   ./setup.sh"
echo ""
echo -e "${GREEN}2. Start Services:${NC}"
echo "   Terminal 1: cd backend && python -m uvicorn app.main:app --reload"
echo "   Terminal 2: cd frontend && streamlit run dashboard.py"
echo ""
echo -e "${GREEN}3. Try the Demo:${NC}"
echo "   python quickstart.py"
echo ""
echo -e "${GREEN}4. Access:${NC}"
echo "   API: http://localhost:8000/docs"
echo "   Dashboard: http://localhost:8501"
echo ""
echo -e "${GREEN}5. Upload Your Circular:${NC}"
echo "   Use the dashboard Upload page or API endpoint"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}RegGraph is ready! Happy compliance tracking! 🚀${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
