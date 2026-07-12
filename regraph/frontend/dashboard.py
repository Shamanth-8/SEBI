"""
Streamlit dashboard for RegGraph - Interactive obligation graph visualization.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime
import httpx
import json
from typing import Dict, List

# Page configuration
st.set_page_config(
    page_title="RegGraph - Regulatory Obligation Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Initialize session state
if 'current_intermediary' not in st.session_state:
    st.session_state.current_intermediary = 'stockbroker'


def get_api_data(endpoint: str) -> Dict:
    """Fetch data from RegGraph API."""
    try:
        response = httpx.get(f"{API_BASE_URL}{endpoint}", timeout=30.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return {}


def main():
    """Main dashboard application."""
    
    # Header
    st.title("📊 RegGraph - Regulatory Obligation Dashboard")
    st.markdown("**Real-time SEBI regulatory compliance tracking through obligation graphs**")
    
    # Sidebar navigation
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Select View",
        [
            "📈 Dashboard Overview",
            "🔍 Search Obligations",
            "📋 Compliance Mapping",
            "🌐 Graph Analysis",
            "⚠️ Evidence Gaps",
            "🔗 Impact Analysis",
            "📤 Upload Circular"
        ]
    )
    
    # Intermediary selector
    st.sidebar.markdown("---")
    intermediary_type = st.sidebar.selectbox(
        "Intermediary Type",
        ["stockbroker", "rta", "investment_adviser"],
        key="intermediary_selector"
    )
    st.session_state.current_intermediary = intermediary_type
    
    # Page content
    if page == "📈 Dashboard Overview":
        show_dashboard_overview(intermediary_type)
    elif page == "🔍 Search Obligations":
        show_search_obligations()
    elif page == "📋 Compliance Mapping":
        show_compliance_mapping(intermediary_type)
    elif page == "🌐 Graph Analysis":
        show_graph_analysis()
    elif page == "⚠️ Evidence Gaps":
        show_evidence_gaps(intermediary_type)
    elif page == "🔗 Impact Analysis":
        show_impact_analysis()
    elif page == "📤 Upload Circular":
        show_upload_circular()


def show_dashboard_overview(intermediary_type: str):
    """Dashboard overview with key metrics."""
    st.header("📊 Compliance Dashboard Overview")
    
    # Fetch statistics
    stats = get_api_data("/graph/statistics")
    
    if stats:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Obligations", stats.get('total_obligations', 0))
        with col2:
            st.metric("Active Obligations", stats.get('active_obligations', 0))
        with col3:
            st.metric("High Severity", stats.get('high_severity_count', 0))
        with col4:
            st.metric("Circulars Ingested", stats.get('circulars_ingested', 0))
        
        st.markdown("---")
        
        # Evidence gaps visualization
        col1, col2 = st.columns(2)
        
        with col1:
            evidence_data = stats.get('evidence_gaps', {})
            fig = go.Figure(data=[
                go.Bar(
                    x=['Complete', 'Partial', 'Missing'],
                    y=[
                        evidence_data.get('complete', 0),
                        evidence_data.get('partial', 0),
                        evidence_data.get('missing', 0)
                    ],
                    marker=dict(color=['#2ecc71', '#f39c12', '#e74c3c'])
                )
            ])
            fig.update_layout(title="Evidence Status Distribution", xaxis_title="Status", yaxis_title="Count")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Obligation status breakdown
            fig = go.Figure(data=[
                go.Pie(
                    labels=['Active', 'Superseded'],
                    values=[stats.get('active_obligations', 0), stats.get('superseded_obligations', 0)],
                    marker=dict(colors=['#3498db', '#95a5a6'])
                )
            ])
            fig.update_layout(title="Obligation Status")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data available. Please upload a circular first.")


def show_search_obligations():
    """Search and filter obligations."""
    st.header("🔍 Search Obligations")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input("Search by keywords, title, or description")
    with col2:
        search_semantic = st.checkbox("Semantic Search", value=True)
    
    if search_query:
        params = f"/obligations/search?query={search_query}&semantic={search_semantic}"
        results = get_api_data(params)
        
        if results.get('results'):
            st.success(f"Found {results.get('results_count', 0)} results")
            
            # Display results as expandable cards
            for obl in results['results']:
                with st.expander(f"📌 {obl['title']} ({obl['severity'].upper()})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Description:** {obl['description']}")
                        st.write(f"**Responsible Party:** {obl['responsible_party']}")
                        st.write(f"**Action:** {obl['required_action']}")
                    with col2:
                        st.write(f"**Status:** {obl['status']}")
                        st.write(f"**Deadline:** {obl['deadline'] or 'TBD'}")
                    
                    st.button("View Details", key=f"btn_{obl['id']}")
        else:
            st.info("No obligations found matching your search.")


def show_compliance_mapping(intermediary_type: str):
    """Show compliance mapping for intermediary."""
    st.header(f"📋 Compliance Mapping - {intermediary_type.upper()}")
    
    mapping = get_api_data(f"/compliance/mapping/{intermediary_type}")
    
    if mapping:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Applicable Obligations",
                mapping.get('applicable_obligations_count', 0)
            )
        with col2:
            st.metric(
                "Not Applicable",
                mapping.get('not_applicable_count', 0)
            )
        with col3:
            st.metric(
                "Critical Gaps",
                mapping.get('critical_gaps_count', 0)
            )
        
        st.markdown("---")
        
        # Action items
        st.subheader("Priority Action Items")
        
        action_items = mapping.get('action_items', [])
        if action_items:
            df_actions = pd.DataFrame([
                {
                    'Priority': item.get('priority', 'normal').upper(),
                    'Responsible': item.get('responsible_party', 'TBD'),
                    'Action': item.get('action', '')[:50] + '...',
                    'Deadline': item.get('deadline', 'TBD'),
                    'Effort': item.get('estimated_effort', 'medium')
                }
                for item in action_items[:10]
            ])
            
            st.dataframe(df_actions, use_container_width=True)
        else:
            st.info("No action items available.")


def show_graph_analysis():
    """Graph structure and dependency analysis."""
    st.header("🌐 Graph Analysis")
    
    stats = get_api_data("/graph/statistics")
    
    if stats:
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total Nodes", stats.get('total_nodes', 0))
            st.metric("Total Edges", stats.get('total_edges', 0))
        with col2:
            st.metric("Network Density", f"{stats.get('network_density', 0):.3f}")
        
        st.markdown("---")
        
        # Search for dependency analysis
        obligation_id = st.text_input("Enter Obligation ID for dependency analysis")
        
        if obligation_id:
            deps = get_api_data(f"/graph/dependencies/{obligation_id}")
            
            if deps:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Direct Dependencies", deps.get('dependency_count', 0))
                with col2:
                    st.metric("Direct Dependents", deps.get('dependent_count', 0))
                with col3:
                    st.metric("Transitive Dependents", deps.get('transitive_dependent_count', 0))
                
                # Display dependency chain
                st.subheader("Dependency Chain")
                
                deps_list = deps.get('direct_dependencies', [])
                if deps_list:
                    st.write("**Depends on:**")
                    for dep in deps_list[:5]:
                        st.write(f"- {dep}")
                else:
                    st.write("No dependencies")
                
                dependents_list = deps.get('direct_dependents', [])
                if dependents_list:
                    st.write("**Required by:**")
                    for dep in dependents_list[:5]:
                        st.write(f"- {dep}")


def show_evidence_gaps(intermediary_type: str):
    """Evidence gap analysis with color coding."""
    st.header("⚠️ Evidence Gaps Analysis")
    
    gaps = get_api_data(f"/compliance/evidence-gaps/{intermediary_type}")
    
    if gaps:
        # Summary cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "✅ Complete",
                gaps['complete'].get('count', 0),
                delta_color="off"
            )
        with col2:
            st.metric(
                "⚠️ Partial",
                gaps['partial'].get('count', 0),
                delta_color="off"
            )
        with col3:
            st.metric(
                "❌ Missing",
                gaps['missing'].get('count', 0),
                delta_color="off"
            )
        
        st.markdown("---")
        
        # Detailed gap breakdown
        tab1, tab2, tab3 = st.tabs(["✅ Complete", "⚠️ Partial", "❌ Missing"])
        
        with tab1:
            st.subheader("Complete Evidence")
            for obl in gaps['complete'].get('obligations', []):
                st.write(f"✅ {obl['title']}")
        
        with tab2:
            st.subheader("Partial Evidence")
            for obl in gaps['partial'].get('obligations', []):
                st.write(f"⚠️ {obl['title']}")
        
        with tab3:
            st.subheader("Missing Evidence (Priority)")
            for obl in gaps['missing'].get('obligations', []):
                severity_emoji = "🔴" if obl['severity'] == 'high' else "🟡"
                st.write(f"{severity_emoji} {obl['title']}")


def show_impact_analysis():
    """Impact propagation analysis."""
    st.header("🔗 Impact Analysis")
    
    obligation_id = st.text_input("Enter Obligation ID to analyze impact")
    
    if obligation_id:
        impact = get_api_data(f"/graph/impact/{obligation_id}")
        
        if impact:
            st.subheader(f"Impact Analysis for {obligation_id}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Directly Affected",
                    len(impact.get('directly_affected', []))
                )
            with col2:
                st.metric(
                    "Indirectly Affected",
                    len(impact.get('indirectly_affected', []))
                )
            with col3:
                total = (
                    len(impact.get('directly_affected', [])) +
                    len(impact.get('indirectly_affected', []))
                )
                st.metric("Total Affected", total)
            
            st.markdown("---")
            
            # Implementation effort
            effort = impact.get('implementation_effort', {})
            if effort:
                st.subheader("Implementation Effort Estimate")
                
                effort_data = {
                    'Effort Level': ['High', 'Medium', 'Low'],
                    'Count': [
                        effort.get('high_effort_count', 0),
                        effort.get('medium_effort_count', 0),
                        effort.get('low_effort_count', 0)
                    ]
                }
                
                fig = go.Figure(data=[
                    go.Bar(
                        x=effort_data['Effort Level'],
                        y=effort_data['Count'],
                        marker=dict(color=['#e74c3c', '#f39c12', '#2ecc71'])
                    )
                ])
                fig.update_layout(title="Implementation Effort Distribution")
                st.plotly_chart(fig, use_container_width=True)


def show_upload_circular():
    """Circular upload interface."""
    st.header("📤 Upload New Regulatory Circular")
    
    st.markdown("""
    Upload a new SEBI regulatory circular or amendment to automatically:
    1. Extract obligations
    2. Compare against existing graph
    3. Propagate impact through dependencies
    4. Generate compliance mappings
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        circular_id = st.text_input("Circular ID (e.g., SEBI/HO/MIRSD/CIR/2024/001)")
        circular_title = st.text_input("Circular Title")
    
    with col2:
        intermediary_types = st.multiselect(
            "Applicable Intermediary Types",
            ["stockbroker", "rta", "investment_adviser"],
            default=["stockbroker"]
        )
    
    # File uploader
    uploaded_file = st.file_uploader("Upload circular document (.txt, .pdf)", type=["txt", "pdf"])
    
    # Or text area
    circular_text = st.text_area(
        "Or paste circular text directly",
        height=300,
        placeholder="Paste the full text of the circular here..."
    )
    
    if st.button("Process Circular", type="primary"):
        if not circular_id or not circular_title:
            st.error("Please provide Circular ID and Title")
        elif not (uploaded_file or circular_text):
            st.error("Please provide circular document or text")
        else:
            with st.spinner("Processing circular..."):
                try:
                    # Get document text
                    if uploaded_file:
                        document_text = uploaded_file.read().decode('utf-8')
                    else:
                        document_text = circular_text
                    
                    # Call API
                    response = httpx.post(
                        f"{API_BASE_URL}/circulars/upload",
                        json={
                            "circular_id": circular_id,
                            "title": circular_title,
                            "document_text": document_text,
                            "intermediary_types": intermediary_types
                        },
                        timeout=60.0
                    )
                    
                    result = response.json()
                    
                    st.success("✅ Circular processed successfully!")
                    
                    # Display results
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Extracted Obligations", result.get('extracted_obligations_count', 0))
                    with col2:
                        st.metric("New Obligations", result.get('new_obligations_count', 0))
                    with col3:
                        st.metric("Modified", result.get('modified_obligations_count', 0))
                    with col4:
                        st.metric("Superseded", result.get('superseded_obligations_count', 0))
                    
                    st.markdown("---")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Impact Score", f"{result.get('impact_score', 0):.2f}")
                    with col2:
                        risk_level = result.get('risk_level', 'medium')
                        risk_color = "🔴" if risk_level == 'high' else "🟡" if risk_level == 'medium' else "🟢"
                        st.write(f"**Risk Level:** {risk_color} {risk_level.upper()}")
                    
                except Exception as e:
                    st.error(f"Error processing circular: {str(e)}")


if __name__ == "__main__":
    main()
