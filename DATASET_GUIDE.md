# 📊 RegGraph Dataset - Quick Start Guide

## ✅ What Was Created

Your SEBI obligations dataset has been generated with 3 formats:

```
✅ CSV Format
   File: data/sebi_obligations_dataset.csv
   Contains: 40 regulatory obligations in spreadsheet format
   
✅ JSON Format
   File: sebi_obligations_dataset.json
   Contains: Full dataset with metadata
   
✅ RegGraph Format
   File: sebi_obligations_regraph.json
   Contains: Optimized for RegGraph system ingestion
```

## 📈 Dataset Highlights

| Metric | Value |
|--------|-------|
| **Total Obligations** | 40 |
| **High/Critical Risk** | 23 (57.5%) |
| **Recurring Tasks** | 23 (57.5%) |
| **Intermediaries Covered** | 3 (Stockbroker, RTA, Adviser) |
| **Responsible Parties** | 10+ different roles |
| **Circulars Modeled** | 15 different SEBI circulars |

### By Intermediary Type

```
📌 STOCKBROKER: 38 obligations
   - 1 Critical
   - 20 High
   - 16 Medium
   - 1 Low

📌 RTA: 26 obligations
   - 1 Critical
   - 11 High
   - 13 Medium
   - 1 Low

📌 INVESTMENT ADVISER: 24 obligations
   - 1 Critical
   - 12 High
   - 11 Medium
```

### Top Compliance Areas

1. **Margin Management** - Daily monitoring, calls, reporting
2. **Know Your Client (KYC)** - Documentation, updates, verification
3. **Risk Management** - Committee oversight, stress testing
4. **Governance** - Board requirements, policies
5. **Fund Management** - Segregation, reconciliation
6. **Settlement** - Guarantee funds, fail management
7. **Reporting** - Exchange, SEBI, client communications
8. **Audit & Compliance** - Internal audits, certifications

## 🚀 How to Use the Dataset

### Option 1: Upload via Dashboard (Easiest)

```bash
1. Start RegGraph (if not already running)
   Terminal 1: cd backend && python -m uvicorn app.main:app --reload
   Terminal 2: cd frontend && streamlit run dashboard.py

2. Open Dashboard
   http://localhost:8501

3. Click "📤 Upload Circular"

4. Fill in the form:
   - Circular ID: SEBI/HO/MRD/CIR/2024/DATASET
   - Title: SEBI Regulatory Obligations Dataset
   - Select: stockbroker, rta, investment_adviser

5. Copy CSV data:
   cat data/sebi_obligations_dataset.csv

6. Paste into "Paste circular text directly" field

7. Click "Process Circular"

8. Wait for processing and view results!
```

### Option 2: Upload via API

```bash
# 1. Load the CSV data
CSV_DATA=$(cat data/sebi_obligations_dataset.csv | head -5)

# 2. Send to RegGraph API
curl -X POST http://localhost:8000/api/v1/circulars/upload \
  -H "Content-Type: application/json" \
  -d '{
    "circular_id": "SEBI/HO/MRD/CIR/2024/DATASET",
    "title": "SEBI Regulatory Obligations Dataset - 40 Obligations",
    "document_text": "Comprehensive dataset of 40 SEBI regulatory obligations covering: Margin management (daily monitoring, margin calls, quarterly reporting), KYC requirements (documentation, annual updates, suitability assessment), Risk management (committee oversight, stress testing, derivative monitoring), Governance (board diversity, independent directors, policies), Fund management (segregation, reconciliation), Settlement procedures, Reporting (exchange, SEBI, clients), Internal audits, Compliance certifications, and more.",
    "intermediary_types": ["stockbroker", "rta", "investment_adviser"]
  }'
```

### Option 3: Direct Python Integration

```python
import json
from pathlib import Path

# Load RegGraph-formatted data
regraph_data = json.load(open('sebi_obligations_regraph.json'))

# Use in your code
print(f"Loaded {len(regraph_data)} obligations")

# Each obligation has:
# - obligation_id, title, description
# - responsible_party, required_action
# - deadline, deadline_type
# - intermediary_types, severity
# - evidence_requirements, keywords
```

## 📊 Insights You Can Get

After uploading, try these queries:

### 1. Search Compliance Obligations
```bash
curl "http://localhost:8000/api/v1/obligations/search?query=KYC&intermediary_type=stockbroker"
```
**Shows**: All KYC-related obligations for stockbrokers

### 2. Get Compliance Dashboard
```bash
curl "http://localhost:8000/api/v1/compliance/dashboard/stockbroker"
```
**Shows**: 
- Total applicable obligations
- Evidence status breakdown
- Severity distribution
- Priority action items

### 3. View Evidence Gaps
```bash
curl "http://localhost:8000/api/v1/compliance/evidence-gaps/stockbroker"
```
**Shows**:
- 🟢 Complete evidence (green)
- 🟡 Partial evidence (yellow)
- 🔴 Missing evidence (red)

### 4. Analyze Impact of Changes
```bash
curl "http://localhost:8000/api/v1/graph/impact/OBL_001"
```
**Shows**:
- Which other obligations are affected
- Ripple effects through compliance
- Implementation effort estimate
- Timeline for changes

### 5. Get Full Network Analysis
```bash
curl "http://localhost:8000/api/v1/graph/statistics"
```
**Shows**:
- Total obligations in system
- Network density
- High-risk obligations
- Evidence gap distribution

## 🎯 Use Cases

### For Compliance Officer
```bash
# Find all high-severity obligations
curl "http://localhost:8000/api/v1/obligations?severity=high&skip=0&limit=50"

# Get gaps that need immediate attention
curl "http://localhost:8000/api/v1/compliance/evidence-gaps/stockbroker"

# Export for audit
curl "http://localhost:8000/api/v1/graph/export/json" > audit_export.json
```

### For Risk Officer
```bash
# Find all risk management obligations
curl "http://localhost:8000/api/v1/obligations/search?query=risk_management"

# Get impact of policy changes
curl "http://localhost:8000/api/v1/graph/impact/OBL_027"  # Stress testing
```

### For Operations Manager
```bash
# Find daily tasks
curl "http://localhost:8000/api/v1/obligations/search?query=daily"

# Get operations-related obligations
curl "http://localhost:8000/api/v1/obligations/search?query=settlement"
```

## 📝 Dataset CSV Columns

```
obligation_id          - Unique identifier (OBL_001, OBL_002, etc.)
circular_id            - Source circular (SEBI/HO/MRD/CIR/2024/XXX)
title                  - Obligation title
description            - Full description of requirement
responsible_party      - Who is responsible (role name)
required_action        - Specific action to take
deadline               - When it's due (date or frequency)
deadline_type          - Type (fixed date, recurring, relative)
intermediary_types     - Which intermediaries (semicolon separated)
evidence_requirements  - What proof is needed (semicolon separated)
severity               - Risk level (critical, high, medium, low)
keywords               - Tags for searching (semicolon separated)
```

## 🔗 Key Obligation Examples

### Margin Management (OBL_001 to OBL_003)
- Daily margin monitoring
- Quarterly margin reporting
- 24-hour margin call execution

### KYC Compliance (OBL_004 to OBL_006)
- New client documentation
- Annual KYC updates
- Suitability assessments

### Risk & Governance (OBL_009 to OBL_015)
- Risk committee meetings
- Stress testing
- Enhanced due diligence

### Fund & Settlement (OBL_016 to OBL_029)
- Segregated accounts
- Monthly reconciliation
- Settlement guarantee funds

### Reporting (OBL_010 to OBL_013, OBL_033)
- Daily exchange reports
- Annual SEBI filings
- Quarterly performance reports
- Compliance certifications

## 🎓 Understanding the Data

### Severity Levels
```
🔴 CRITICAL (1) - Must do immediately, regulatory requirement
🔴 HIGH (22)   - Core compliance obligations
🟡 MEDIUM (16) - Important but slightly flexible
🟢 LOW (1)     - Informational or administrative
```

### Deadline Types
```
⏰ RECURRING (23) - Must do regularly (daily, monthly, quarterly)
📅 FIXED (8)     - Specific dates (end of quarter, annual)
⚡ RELATIVE (9)  - Based on event (before transaction, within X days)
```

### Evidence Requirements
```
Examples:
- Exchange receipts
- Signed reports
- Bank confirmations
- Audit documentation
- Policy documents
- Training certificates
- Approval memos
```

## 💡 Pro Tips

1. **Start with high-severity items**: Focus on the 23 high/critical obligations first

2. **Group by responsible party**: The Compliance Officer has 12 obligations - consider workload

3. **Track recurring tasks**: 57.5% are recurring - automate these if possible

4. **Evidence collection**: Many obligations need documented proof - set up processes

5. **Use semantic search**: Try searching for related terms to find connected obligations

## 🐛 Troubleshooting

### Data not appearing in dashboard?
```bash
# Check API is running
curl http://localhost:8000/health

# Try re-uploading with different circular ID
# Verify all fields are filled correctly
```

### Search not finding obligations?
```bash
# Try simpler search terms
curl "http://localhost:8000/api/v1/obligations/search?query=compliance"

# Check keyword field in CSV for better matches
```

### Evidence gaps not showing?
```bash
# Verify compliance dashboard loads
curl "http://localhost:8000/api/v1/compliance/dashboard/stockbroker"

# Check that evidence_status field is populated
```

## 📚 Next Steps

1. ✅ Upload the dataset to RegGraph
2. ✅ Explore the compliance dashboard
3. ✅ Search for obligations in your area
4. ✅ Analyze impact relationships
5. ✅ Export data for further analysis
6. ✅ Set up tracking for evidence collection

## 🚀 Want More Data?

To create additional datasets:

```bash
# Modify the CSV and run analyzer again
python analyze_dataset.py

# Or add more rows to the CSV:
# - Copy an existing row
# - Update: obligation_id, title, description
# - Re-run analyzer to generate new exports
```

---

**You're all set! Start exploring your compliance data with RegGraph! 🎉**

For questions or issues, check the main README.md or ARCHITECTURE.md files.
