#!/usr/bin/env python
"""
CSV Dataset Analyzer for RegGraph
Converts CSV obligation data into RegGraph-compatible format and provides insights.
"""

import csv
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

def load_csv_dataset(filepath):
    """Load obligations from CSV file."""
    obligations = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            obligations.append(row)
    return obligations

def analyze_dataset(obligations):
    """Analyze the obligation dataset and provide insights."""
    
    print("\n" + "="*80)
    print("📊 SEBI OBLIGATIONS DATASET ANALYSIS")
    print("="*80)
    
    # Basic Statistics
    print(f"\n📈 DATASET OVERVIEW")
    print(f"  Total Obligations: {len(obligations)}")
    
    # By Intermediary Type
    intermediary_counts = Counter()
    for obl in obligations:
        types = [t.strip() for t in obl['intermediary_types'].split(';')]
        for itype in types:
            intermediary_counts[itype] += 1
    
    print(f"\n👥 BY INTERMEDIARY TYPE")
    for itype, count in sorted(intermediary_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {itype}: {count} obligations")
    
    # By Severity
    severity_counts = Counter()
    for obl in obligations:
        severity_counts[obl['severity']] += 1
    
    print(f"\n⚠️  BY SEVERITY")
    for severity, count in sorted(severity_counts.items(), reverse=True):
        emoji = "🔴" if severity == "critical" else "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
        print(f"  {emoji} {severity.upper()}: {count}")
    
    # By Responsible Party
    party_counts = Counter()
    for obl in obligations:
        party_counts[obl['responsible_party']] += 1
    
    print(f"\n👔 TOP RESPONSIBLE PARTIES")
    for party, count in party_counts.most_common(10):
        print(f"  {party}: {count} obligations")
    
    # By Circular
    circular_counts = Counter()
    for obl in obligations:
        circular_counts[obl['circular_id']] += 1
    
    print(f"\n📋 BY CIRCULAR")
    for circular, count in sorted(circular_counts.items()):
        print(f"  {circular}: {count} obligations")
    
    # Deadline Types
    deadline_types = Counter()
    for obl in obligations:
        deadline_types[obl['deadline_type']] += 1
    
    print(f"\n⏰ DEADLINE TYPES")
    for dtype, count in sorted(deadline_types.items()):
        print(f"  {dtype.upper()}: {count}")
    
    # Keywords Analysis
    keywords = Counter()
    for obl in obligations:
        kw_list = [k.strip() for k in obl['keywords'].split(';')]
        keywords.update(kw_list)
    
    print(f"\n🔑 TOP KEYWORDS")
    for kw, count in keywords.most_common(15):
        print(f"  {kw}: {count}")
    
    # Evidence Requirements
    evidence_categories = Counter()
    for obl in obligations:
        evidence = [e.strip() for e in obl['evidence_requirements'].split(';')]
        evidence_categories.update(evidence)
    
    print(f"\n📄 TOP EVIDENCE REQUIREMENTS")
    for evidence, count in evidence_categories.most_common(10):
        print(f"  {evidence}: {count}")
    
    # Compliance Gaps Analysis
    print(f"\n🚨 COMPLIANCE READINESS ANALYSIS")
    high_risk = len([o for o in obligations if o['severity'] in ['critical', 'high']])
    print(f"  High/Critical Risk: {high_risk} ({high_risk/len(obligations)*100:.1f}%)")
    
    recurring = len([o for o in obligations if o['deadline_type'] == 'recurring'])
    print(f"  Recurring Tasks: {recurring} ({recurring/len(obligations)*100:.1f}%)")
    
    high_party = party_counts.most_common(1)[0]
    print(f"  Most Burdened Party: {high_party[0]} ({high_party[1]} obligations)")

def export_to_json(obligations, output_path):
    """Export dataset to JSON format."""
    json_data = {
        'metadata': {
            'extracted_at': datetime.now().isoformat(),
            'total_obligations': len(obligations),
            'format_version': '1.0'
        },
        'obligations': obligations
    }
    
    with open(output_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"\n✅ Exported to JSON: {output_path}")

def export_to_regraph_format(obligations, output_path):
    """Export as RegGraph-compatible format."""
    regraph_format = []
    
    for i, obl in enumerate(obligations, 1):
        regraph_obl = {
            'obligation_id': obl['obligation_id'],
            'circular_id': obl['circular_id'],
            'clause_reference': f"{obl['circular_id']} - {obl['title'][:30]}",
            'title': obl['title'],
            'description': obl['description'],
            'responsible_party': obl['responsible_party'],
            'required_action': obl['required_action'],
            'deadline': obl['deadline'],
            'deadline_type': obl['deadline_type'],
            'intermediary_types': [t.strip() for t in obl['intermediary_types'].split(';')],
            'evidence_requirements': [e.strip() for e in obl['evidence_requirements'].split(';')],
            'evidence_status': 'red',  # Default to missing
            'severity': obl['severity'],
            'status': 'active',
            'keywords': [k.strip() for k in obl['keywords'].split(';')]
        }
        regraph_format.append(regraph_obl)
    
    with open(output_path, 'w') as f:
        json.dump(regraph_format, f, indent=2)
    
    print(f"✅ Exported to RegGraph format: {output_path}")

def create_compliance_dashboard(obligations):
    """Create a compliance dashboard summary."""
    
    print("\n" + "="*80)
    print("📊 COMPLIANCE DASHBOARD")
    print("="*80)
    
    # By Intermediary - Detailed View
    intermediary_map = defaultdict(lambda: {'high': 0, 'medium': 0, 'low': 0, 'critical': 0, 'total': 0})
    
    for obl in obligations:
        types = [t.strip() for t in obl['intermediary_types'].split(';')]
        severity = obl['severity']
        
        for itype in types:
            intermediary_map[itype][severity] += 1
            intermediary_map[itype]['total'] += 1
    
    for itype in sorted(intermediary_map.keys()):
        stats = intermediary_map[itype]
        print(f"\n🏢 {itype.upper()}")
        print(f"  Total Obligations: {stats['total']}")
        if stats['critical'] > 0:
            print(f"  🔴 Critical: {stats['critical']}")
        if stats['high'] > 0:
            print(f"  🔴 High: {stats['high']}")
        if stats['medium'] > 0:
            print(f"  🟡 Medium: {stats['medium']}")
        if stats['low'] > 0:
            print(f"  🟢 Low: {stats['low']}")

def main():
    """Main execution."""
    
    # Try multiple possible paths
    possible_paths = [
        Path(__file__).parent / 'data' / 'sebi_obligations_dataset.csv',
        Path(__file__).parent / 'sebi_obligations_dataset.csv',
        Path.cwd() / 'data' / 'sebi_obligations_dataset.csv',
    ]
    
    csv_path = None
    for path in possible_paths:
        if path.exists():
            csv_path = path
            break
    
    if csv_path is None:
        print(f"❌ CSV file not found in any of:")
        for path in possible_paths:
            print(f"   - {path}")
        return
    
    print(f"📂 Loading dataset from: {csv_path}")
    obligations = load_csv_dataset(csv_path)
    
    # Analyze
    analyze_dataset(obligations)
    
    # Create dashboard
    create_compliance_dashboard(obligations)
    
    # Export formats
    output_dir = Path(__file__).parent
    
    json_path = output_dir / 'sebi_obligations_dataset.json'
    export_to_json(obligations, json_path)
    
    regraph_path = output_dir / 'sebi_obligations_regraph.json'
    export_to_regraph_format(obligations, regraph_path)
    
    # Usage instructions
    print("\n" + "="*80)
    print("🚀 HOW TO USE THIS DATA")
    print("="*80)
    
    print(f"""
✅ Files Generated:
   1. {csv_path} - Original CSV format
   2. {json_path} - JSON format
   3. {regraph_path} - RegGraph-compatible JSON

📊 To Upload to RegGraph:

   Option 1: Via API
   ─────────────────
   curl -X POST http://localhost:8000/api/v1/circulars/upload \\
     -H "Content-Type: application/json" \\
     -d '{{
       "circular_id": "SEBI/HO/MRD/CIR/2024/DATASET",
       "title": "SEBI Regulatory Obligations Dataset",
       "document_text": "40 comprehensive SEBI obligations covering margin management, KYC, compliance, governance, and risk management.",
       "intermediary_types": ["stockbroker", "rta", "investment_adviser"]
     }}'

   Option 2: Via Dashboard
   ──────────────────────
   1. Go to http://localhost:8501
   2. Click "📤 Upload Circular"
   3. Enter:
      - Circular ID: SEBI/HO/MRD/CIR/2024/DATASET
      - Title: SEBI Obligations Dataset
      - Select intermediary types
   4. Paste or upload the data
   5. Click "Process Circular"

📈 Get Insights:

   1. Search Obligations
      curl "http://localhost:8000/api/v1/obligations/search?query=margin"

   2. Get Compliance Dashboard
      curl "http://localhost:8000/api/v1/compliance/dashboard/stockbroker"

   3. View Evidence Gaps
      curl "http://localhost:8000/api/v1/compliance/evidence-gaps/stockbroker"

   4. Analyze Impact
      curl "http://localhost:8000/api/v1/graph/impact/OBL_001"

   5. Export Full Graph
      curl "http://localhost:8000/api/v1/graph/export/json" > graph.json

📝 Dataset Contents:

   - 40 SEBI regulatory obligations
   - 5 circulars (2024 issues)
   - 3 intermediary types
   - Multiple compliance areas:
     * Margin management
     * Know Your Client (KYC)
     * Risk management
     * Governance
     * Fund management
     * Settlement
     * Reporting
     * Audit & compliance
""")
    
    print("="*80)
    print("✨ Dataset ready for analysis!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
