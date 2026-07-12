#!/usr/bin/env python
"""
Quick start script for RegGraph.
Demonstrates the full pipeline with a sample circular.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.agents.orchestrator import RegGraphOrchestrator
from data.sample_circular import SAMPLE_CIRCULAR, SAMPLE_INTERMEDIARY_PROFILE
import json
from datetime import datetime

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def main():
    """Run the RegGraph demo."""
    
    print_section("RegGraph - Regulatory Obligation Dependency Graph Demo")
    print("\nThis demo will:")
    print("1. Initialize the obligation graph")
    print("2. Process a sample SEBI Stockbroker circular")
    print("3. Extract obligations and build dependency graph")
    print("4. Perform semantic diff (simulated)")
    print("5. Generate compliance mappings")
    print("6. Display impact analysis")
    
    # Initialize orchestrator
    print_section("Step 1: Initializing RegGraph Orchestrator")
    try:
        orchestrator = RegGraphOrchestrator()
        print("✅ Orchestrator initialized successfully")
        print(f"   Current graph size: {orchestrator.graph.get_statistics()['total_obligations']} obligations")
    except Exception as e:
        print(f"❌ Error initializing orchestrator: {e}")
        return
    
    # Process the sample circular
    print_section("Step 2: Processing Sample Stockbroker Circular")
    print("📄 Processing: Master Circular - Stockbrokers")
    print(f"   Document size: {len(SAMPLE_CIRCULAR)} characters")
    
    try:
        result = orchestrator.process_circular(
            circular_text=SAMPLE_CIRCULAR,
            circular_id="SEBI/HO/MRD/CIR/2024/SAMPLE",
            circular_title="Master Circular - Stockbrokers",
            intermediary_types=["stockbroker", "rta"]
        )
        
        print("✅ Circular processed successfully")
        
        # Display extraction results
        print_section("Step 3: Obligation Extraction Results")
        extracted = result['extracted_obligations']
        print(f"📊 Total obligations extracted: {len(extracted)}")
        print(f"\n   Sample obligations:")
        for obl in extracted[:3]:
            print(f"\n   📌 {obl.title}")
            print(f"      ID: {obl.obligation_id}")
            print(f"      Responsible: {obl.responsible_party}")
            print(f"      Deadline: {obl.deadline or 'Not specified'}")
            print(f"      Severity: {obl.severity}")
            print(f"      Evidence needed: {', '.join(obl.evidence_requirements[:2])}")
        
        # Display diff results
        print_section("Step 4: Semantic Diff Results")
        diff = result['diff_result']
        print(f"📊 New obligations: {len(diff.new_obligations)}")
        print(f"   Modified obligations: {len(diff.modified_obligations)}")
        print(f"   Superseded obligations: {len(diff.superseded_obligations)}")
        print(f"   Overall impact score: {diff.impact_score:.2f}")
        
        # Display impact propagation
        print_section("Step 5: Impact Propagation Analysis")
        propagation = result['impact_propagation']
        print(f"📊 Directly affected: {len(propagation['directly_affected'])} obligations")
        print(f"   Indirectly affected: {len(propagation['indirectly_affected'])} obligations")
        print(f"   Total affected: {propagation['total_affected_count']} obligations")
        if propagation['affected_workflows']:
            print(f"   Affected workflows: {', '.join(propagation['affected_workflows'][:3])}")
        
        # Display graph statistics
        print_section("Step 6: Updated Graph Statistics")
        stats = result['graph_stats']
        print(f"📊 Total obligations: {stats['total_obligations']}")
        print(f"   Total graph nodes: {stats['total_nodes']}")
        print(f"   Total graph edges: {stats['total_edges']}")
        print(f"   Active obligations: {stats['active_obligations']}")
        print(f"   Superseded obligations: {stats['superseded_obligations']}")
        print(f"   High severity count: {stats['high_severity_count']}")
        print(f"   Evidence gaps:")
        print(f"      ✅ Complete: {stats['evidence_gaps']['complete']}")
        print(f"      ⚠️  Partial: {stats['evidence_gaps']['partial']}")
        print(f"      ❌ Missing: {stats['evidence_gaps']['missing']}")
        
        # Display compliance mapping
        print_section("Step 7: Compliance Mapping for Stockbroker")
        stockbroker_mapping = result['compliance_mappings'].get('stockbroker')
        if stockbroker_mapping:
            print(f"📊 Applicable obligations: {len(stockbroker_mapping.applicable_obligations)}")
            print(f"   Not applicable: {len(stockbroker_mapping.not_applicable_obligations)}")
            print(f"   Critical gaps: {len(stockbroker_mapping.critical_gaps)}")
            
            if stockbroker_mapping.action_items:
                print(f"\n   Top priority action items:")
                for item in stockbroker_mapping.action_items[:3]:
                    print(f"\n   🎯 {item.get('action', 'N/A')[:60]}")
                    print(f"      Responsible: {item.get('responsible_party')}")
                    print(f"      Deadline: {item.get('deadline')}")
                    print(f"      Priority: {item.get('priority')}")
        
        # Display impact report
        print_section("Step 8: Change Impact Report")
        report = result['impact_report']
        print(f"📋 Circular: {report.circular_id}")
        print(f"   Generated: {report.report_generated_at}")
        print(f"\n   Impact Summary:")
        print(f"      New obligations: {report.new_obligations_count}")
        print(f"      Modified obligations: {report.modified_obligations_count}")
        print(f"      Superseded obligations: {report.superseded_obligations_count}")
        print(f"\n   Risk Assessment:")
        print(f"      Overall impact score: {report.overall_impact_score:.2f}/1.00")
        print(f"      Risk level: {report.risk_level.upper()}")
        if report.affected_workflows:
            print(f"      Affected workflows: {', '.join(report.affected_workflows[:3])}")
        
        # Demonstrate search functionality
        print_section("Step 9: Searching Obligations")
        search_results = orchestrator.search_obligations(
            query="margin reporting",
            intermediary_type="stockbroker",
            use_semantic=False
        )
        print(f"🔍 Search query: 'margin reporting'")
        print(f"   Results found: {len(search_results)}")
        for obl in search_results[:2]:
            print(f"\n   📌 {obl.title}")
            print(f"      {obl.description[:100]}...")
        
        # Demonstrate graph queries
        print_section("Step 10: Graph Analysis Sample")
        if extracted:
            sample_obl_id = extracted[0].obligation_id
            details = orchestrator.get_obligation_details(sample_obl_id)
            if details:
                print(f"📊 Analyzing obligation: {details['obligation'].title}")
                print(f"   Direct dependencies: {len(details['direct_dependencies'])}")
                print(f"   Direct dependents: {len(details['direct_dependents'])}")
                print(f"   Transitive dependents: {len(details['transitive_dependents'])}")
        
        # API URLs
        print_section("Next Steps")
        print("\n🚀 The application is ready! To interact with it:")
        print("\n1. Start the FastAPI backend:")
        print("   cd backend && python -m uvicorn app.main:app --reload")
        print("\n2. Start the Streamlit dashboard (in another terminal):")
        print("   cd frontend && streamlit run dashboard.py")
        print("\n3. Access the services:")
        print("   API Docs: http://localhost:8000/docs")
        print("   Dashboard: http://localhost:8501")
        print("\n4. Example API calls:")
        print("   GET  /api/v1/graph/statistics")
        print("   GET  /api/v1/obligations/search?query=margin")
        print("   GET  /api/v1/compliance/dashboard/stockbroker")
        print("   GET  /api/v1/compliance/evidence-gaps/stockbroker")
        
        print_section("Demo Complete ✅")
        print("\nThe obligation graph has been built and is ready for:")
        print("- Real-time circular uploads and processing")
        print("- Semantic searching of obligations")
        print("- Impact analysis and propagation")
        print("- Compliance mapping for any intermediary type")
        print("- Evidence gap tracking and closure")
        
    except Exception as e:
        print(f"❌ Error processing circular: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
