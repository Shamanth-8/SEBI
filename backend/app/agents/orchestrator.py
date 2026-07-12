"""
LangGraph orchestration pipeline for RegGraph.
Wires together all agents for end-to-end processing.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.obligation import (
    Obligation, CircularMetadata, DiffResult, ChangeImpactReport, ObligationStatus
)
from app.agents.extraction_agent import ObligationExtractionAgent
from app.agents.diff_agent import SemanticDiffAgent
from app.agents.impact_propagation import ImpactPropagationEngine
from app.agents.mapping_agent import ComplianceMappingAgent
from app.graph.obligation_graph import ObligationGraph
from app.retrieval.faiss_search import FAISSRetrieval
from app.audit import log_event
from app.metrics import record_pipeline_run, format_summary

logger = logging.getLogger(__name__)


class RegGraphOrchestrator:
    """
    Main orchestration engine for RegGraph.
    Coordinates all agents through the processing pipeline.
    """
    
    def __init__(self, obligation_graph: Optional[ObligationGraph] = None):
        """Initialize orchestrator with all agents."""
        self.graph = obligation_graph or ObligationGraph()
        self.graph.load()  # Try to load existing graph
        
        # Initialize agents
        self.extraction_agent = ObligationExtractionAgent()
        self.diff_agent = SemanticDiffAgent(self.graph)
        self.impact_engine = ImpactPropagationEngine(self.graph)
        self.mapping_agent = ComplianceMappingAgent(self.graph)
        self.retrieval = FAISSRetrieval()
        
        logger.info("RegGraphOrchestrator initialized")
    
    def process_circular(
        self,
        circular_text: str,
        circular_id: str,
        circular_title: str,
        intermediary_types: Optional[List[str]] = None,
        pages: int = 0,
    ) -> Dict[str, Any]:
        """
        End-to-end processing of a new regulatory circular.

        Pipeline:
        1. Extract obligations from circular
        2. Semantic diff against existing graph
        3. Propagate impact through dependencies
        4. Generate compliance mappings
        5. Create impact report
        """
        pipeline_start = time.perf_counter()

        log_event(
            "CIRCULAR_UPLOAD_STARTED",
            circular_id,
            {"title": circular_title, "text_length": len(circular_text),
             "intermediary_types": intermediary_types},
        )

        logger.info(f"Processing circular {circular_id}: {circular_title}")

        try:
            # Step 1: Extract obligations
            logger.info("Step 1: Extracting obligations...")
            t0 = time.perf_counter()
            new_obligations = self.extraction_agent.extract_obligations(
                circular_text, circular_id, circular_title, intermediary_types
            )
            extraction_seconds = round(time.perf_counter() - t0, 3)
            chunks_processed = max(1, len(circular_text) // 3000)
            logger.info(f"Extracted {len(new_obligations)} obligations in {extraction_seconds}s")

            log_event(
                "EXTRACTION_COMPLETE", circular_id,
                {"obligations_extracted": len(new_obligations),
                 "seconds": extraction_seconds,
                 "chunks": chunks_processed},
            )

            # Add to retrieval index
            for obl in new_obligations:
                self.retrieval.add_clause_embedding(obl.obligation_id, obl.description)

            # Step 2: Semantic diff
            logger.info("Step 2: Performing semantic diff...")
            t0 = time.perf_counter()
            diff_result = self.diff_agent.diff_obligations(new_obligations)
            diff_seconds = round(time.perf_counter() - t0, 3)
            logger.info(
                f"Diff: {len(diff_result.new_obligations)} new, "
                f"{len(diff_result.modified_obligations)} modified, "
                f"{len(diff_result.superseded_obligations)} superseded  [{diff_seconds}s]"
            )

            log_event(
                "DIFF_COMPLETE", circular_id,
                {"new": len(diff_result.new_obligations),
                 "modified": len(diff_result.modified_obligations),
                 "superseded": len(diff_result.superseded_obligations),
                 "impact_score": diff_result.impact_score,
                 "seconds": diff_seconds},
            )

            # Step 3: Add new obligations to graph
            logger.info("Step 3: Adding obligations to graph...")
            for obl in new_obligations:
                self.graph.add_obligation(obl)
            for obl in new_obligations:
                for related_id in obl.related_obligations:
                    self.graph.add_edge(obl.obligation_id, related_id, edge_type="related")
            for superseded_id in diff_result.superseded_obligations:
                superseding_ids = [
                    o.obligation_id for o in diff_result.modified_obligations
                    if o.get('old_id') == superseded_id
                ]
                self.graph.mark_superseded(superseded_id, superseding_ids)

            # Step 4: Propagate impact
            logger.info("Step 4: Propagating impact...")
            t0 = time.perf_counter()
            changed_ids = [o.obligation_id for o in new_obligations]
            propagation = self.impact_engine.propagate_impact(changed_ids, "new")
            impact_seconds = round(time.perf_counter() - t0, 3)
            affected_count = propagation.get('total_affected_count', 0)

            log_event(
                "IMPACT_PROPAGATION_COMPLETE", circular_id,
                {"affected_obligations": affected_count, "seconds": impact_seconds},
            )

            # Step 5: Generate compliance mappings
            logger.info("Step 5: Generating compliance mappings...")
            t0 = time.perf_counter()
            compliance_mappings = {}
            if intermediary_types:
                for itype in intermediary_types:
                    compliance_mappings[itype] = self.mapping_agent.map_obligations_to_intermediary(
                        itype, new_obligations
                    )
            mapping_seconds = round(time.perf_counter() - t0, 3)

            # Count evidence gaps
            evidence_gaps = sum(
                1 for o in new_obligations
                if o.evidence_status.value == "red"
            )

            log_event(
                "COMPLIANCE_MAPPING_COMPLETE", circular_id,
                {"intermediary_types": intermediary_types,
                 "evidence_gaps": evidence_gaps,
                 "seconds": mapping_seconds},
            )

            # Step 6: Generate impact report
            logger.info("Step 6: Generating impact report...")
            impact_report = self._generate_impact_report(
                circular_id, diff_result, propagation, compliance_mappings
            )

            # Step 7: Save state
            logger.info("Step 7: Saving state...")
            self.graph.save()
            self.retrieval.save_index()

            total_seconds = round(time.perf_counter() - pipeline_start, 3)

            # Record metrics
            metrics_record = record_pipeline_run(
                circular_id=circular_id,
                circular_title=circular_title,
                pages=pages,
                text_length=len(circular_text),
                chunks_processed=chunks_processed,
                extraction_seconds=extraction_seconds,
                obligations_extracted=len(new_obligations),
                diff_seconds=diff_seconds,
                new_count=len(diff_result.new_obligations),
                modified_count=len(diff_result.modified_obligations),
                superseded_count=len(diff_result.superseded_obligations),
                impact_seconds=impact_seconds,
                affected_obligations=affected_count,
                mapping_seconds=mapping_seconds,
                intermediary_types=intermediary_types or [],
                evidence_gaps=evidence_gaps,
                total_seconds=total_seconds,
                impact_score=impact_report.overall_impact_score,
                risk_level=impact_report.risk_level,
            )

            log_event(
                "CIRCULAR_PROCESSING_COMPLETE", circular_id,
                {"total_seconds": total_seconds,
                 "obligations_extracted": len(new_obligations),
                 "risk_level": impact_report.risk_level},
            )

            logger.info(f"Circular processing complete for {circular_id} in {total_seconds}s")
            logger.info("\n" + format_summary(metrics_record))

            return {
                'circular_id': circular_id,
                'extracted_obligations': new_obligations,
                'diff_result': diff_result,
                'impact_propagation': propagation,
                'compliance_mappings': compliance_mappings,
                'impact_report': impact_report,
                'graph_stats': self.graph.get_statistics(),
                'metrics': metrics_record,
            }

        except Exception as exc:
            total_seconds = round(time.perf_counter() - pipeline_start, 3)
            log_event(
                "CIRCULAR_PROCESSING_FAILED", circular_id,
                {"total_seconds": total_seconds},
                status="failure",
                error=str(exc),
            )
            raise

    
    def _generate_impact_report(
        self,
        circular_id: str,
        diff_result: DiffResult,
        propagation: Dict,
        compliance_mappings: Dict
    ) -> ChangeImpactReport:
        """Generate comprehensive impact report."""
        
        # Identify affected workflows
        affected_workflows = set(propagation.get('affected_workflows', []))
        
        # Identify affected teams based on responsible parties
        affected_teams = set()
        
        # Build timeline for implementation
        timeline = self.impact_engine.get_impact_timeline(
            list(propagation.get('directly_affected', []))
        )
        
        # Get effort estimate
        effort = self.impact_engine.calculate_implementation_effort(
            list(propagation.get('directly_affected', []))
        )
        
        # Determine risk level
        total_affected = propagation.get('total_affected_count', 0)
        high_severity_count = len([
            o for o in list(diff_result.new_obligations) +
            [m['new_obligation'] for m in diff_result.modified_obligations]
            if o.severity == 'high'
        ])
        
        if high_severity_count > 0 or total_affected > 20:
            risk_level = 'high'
        elif total_affected > 10:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Priority actions
        priority_actions = []
        for obl in diff_result.new_obligations:
            if obl.severity == 'high':
                priority_actions.append({
                    'obligation_id': obl.obligation_id,
                    'action': obl.required_action,
                    'deadline': obl.deadline or 'TBD',
                    'priority': 'critical'
                })
        
        report = ChangeImpactReport(
            circular_id=circular_id,
            report_generated_at=datetime.now(),
            new_obligations_count=len(diff_result.new_obligations),
            modified_obligations_count=len(diff_result.modified_obligations),
            superseded_obligations_count=len(diff_result.superseded_obligations),
            affected_workflows=list(affected_workflows),
            affected_teams=list(affected_teams),
            overall_impact_score=diff_result.impact_score,
            risk_level=risk_level,
            priority_actions=priority_actions,
            implementation_timeline={}
        )
        
        return report
    
    def get_compliance_dashboard(
        self,
        intermediary_type: str
    ) -> Dict[str, Any]:
        """Get compliance dashboard for an intermediary."""
        return self.mapping_agent.get_intermediary_compliance_dashboard(intermediary_type)
    
    def search_obligations(
        self,
        query: str,
        intermediary_type: Optional[str] = None,
        use_semantic: bool = True
    ) -> List[Obligation]:
        """Search obligations by query."""
        
        if use_semantic:
            # Use semantic search first
            similar_ids = self.retrieval.search_similar(query)
            results = [
                self.graph.get_obligation(obl_id)
                for obl_id, _ in similar_ids
                if self.graph.get_obligation(obl_id)
            ]
        else:
            # Use keyword search
            results = self.graph.search_obligations(query, intermediary_type)
        
        return results
    
    def get_graph_statistics(self) -> Dict:
        """Get overall graph statistics."""
        return self.graph.get_statistics()
    
    def get_obligation_details(self, obligation_id: str) -> Optional[Dict]:
        """Get detailed information about an obligation."""
        obligation = self.graph.get_obligation(obligation_id)
        
        if not obligation:
            return None
        
        # Get dependencies
        dependencies = self.graph.get_dependencies(obligation_id)
        dependents = self.graph.get_dependent_obligations(obligation_id)
        
        # Get impact info
        transitive_dependents = self.graph.get_transitive_dependents(obligation_id)
        
        return {
            'obligation': obligation,
            'direct_dependencies': dependencies,
            'direct_dependents': dependents,
            'transitive_dependents': list(transitive_dependents),
            'dependency_count': len(list(transitive_dependents))
        }
