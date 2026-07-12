#!/bin/bash
# Quick setup and run script for RegGraph

set -e

echo "======================================"
echo "RegGraph - Quick Start Setup"
echo "======================================"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $python_version"

# Create data directory
mkdir -p data
echo "✅ Created data directory"

# Check if venv exists, if not create it
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null
echo "✅ Virtual environment activated"

# Upgrade pip
pip install --upgrade pip --quiet

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "   Please edit .env and add your ANTHROPIC_API_KEY"
    echo "   Then run this script again"
    exit 1
else
    echo "✅ .env file exists"
fi

echo ""
echo "======================================"
echo "✅ Setup Complete!"
echo "======================================"
echo ""
echo "To run the application:"
echo ""
echo "1. Terminal 1 - Backend API:"
echo "   cd backend && python -m uvicorn app.main:app --reload"
echo ""
echo "2. Terminal 2 - Dashboard:"
echo "   cd frontend && streamlit run dashboard.py"
echo ""
echo "3. Terminal 3 - Demo (Optional):"
echo "   python quickstart.py"
echo ""
echo "API Documentation: http://localhost:8000/docs"
echo "Dashboard: http://localhost:8501"
echo ""
