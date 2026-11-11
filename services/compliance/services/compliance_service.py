"""Core compliance evaluation service."""

import asyncio
from typing import List, Dict, Any
import structlog
from datetime import datetime

from ...shared.models import AISystem
from ...shared.schemas import ComplianceResult, TestResultResponse, RiskLevel
from ...shared.exceptions import ValidationError, ExternalServiceError
from ..framework.core.base import BaseEvaluator
from .rag_service import RAGService

logger = structlog.get_logger()

class ComplianceService:
    """Service for AI compliance evaluation and testing."""
    
    def __init__(self):
        self.rag_service = RAGService()
    
    async def evaluate_system(
        self,
        ai_system: AISystem,
        evaluator: BaseEvaluator,
        test_config: Dict[str, Any]
    ) -> ComplianceResult:
        """Evaluate an AI system for compliance."""
        
        logger.info("Starting compliance evaluation", 
                   system_id=ai_system.system_id, 
                   evaluator=evaluator.__class__.__name__)
        
        try:
            # Initialize evaluator
            await evaluator.initialize(test_config)
            
            # Get test cases from evaluator
            test_cases = await evaluator.get_test_cases()
            
            # Run tests
            test_results = []
            for test_case in test_cases:
                try:
                    result = await self._run_test_case(ai_system, evaluator, test_case)
                    test_results.append(result)
                except Exception as e:
                    logger.error("Test case failed", 
                               test_case=test_case.get("name", "unknown"), 
                               error=str(e))
                    # Create failed result
                    failed_result = TestResultResponse(
                        result_id=0,  # Will be set when saved to DB
                        test_id=0,   # Will be set when saved to DB
                        score=0.0,
                        passed=False,
                        details={"error": str(e), "test_case": test_case},
                        recommendations=[f"Fix error: {str(e)}"],
                        created_at=datetime.utcnow()
                    )
                    test_results.append(failed_result)
            
            # Calculate overall compliance
            overall_score = self._calculate_overall_score(test_results)
            framework_compliance = await evaluator.calculate_framework_compliance(test_results)
            recommendations = await self._generate_recommendations(ai_system, test_results, evaluator)
            risk_assessment = self._assess_risk_level(overall_score, test_results)
            
            result = ComplianceResult(
                overall_score=overall_score,
                framework_compliance=framework_compliance,
                test_results=test_results,
                recommendations=recommendations,
                risk_assessment=risk_assessment
            )
            
            logger.info("Compliance evaluation completed", 
                       system_id=ai_system.system_id,
                       overall_score=overall_score,
                       risk_level=risk_assessment)
            
            return result
            
        except Exception as e:
            logger.error("Compliance evaluation failed", 
                        system_id=ai_system.system_id, error=str(e))
            raise ValidationError(f"Compliance evaluation failed: {str(e)}")
    
    async def _run_test_case(
        self,
        ai_system: AISystem,
        evaluator: BaseEvaluator,
        test_case: Dict[str, Any]
    ) -> TestResultResponse:
        """Run a single test case."""
        
        test_name = test_case.get("name", "Unknown Test")
        logger.debug("Running test case", test_name=test_name)
        
        try:
            # Execute the test case
            result = await evaluator.execute_test(ai_system, test_case)
            
            # Enhance with RAG if available
            if test_case.get("use_rag", False):
                enhanced_result = await self._enhance_with_rag(result, test_case)
                result.update(enhanced_result)
            
            # Create test result
            test_result = TestResultResponse(
                result_id=0,  # Will be set when saved to DB
                test_id=0,   # Will be set when saved to DB
                score=result.get("score", 0.0),
                passed=result.get("passed", False),
                details=result.get("details", {}),
                recommendations=result.get("recommendations", []),
                created_at=datetime.utcnow()
            )
            
            return test_result
            
        except Exception as e:
            logger.error("Test case execution failed", 
                        test_name=test_name, error=str(e))
            raise
    
    async def _enhance_with_rag(
        self,
        result: Dict[str, Any],
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance test results with RAG-based analysis."""
        
        try:
            # Query RAG service for relevant compliance information
            query = f"Compliance analysis for {test_case.get('category', 'general')} test"
            rag_context = await self.rag_service.query_compliance_docs(
                query, 
                framework=test_case.get("framework", "GDPR")
            )
            
            # Enhance recommendations with RAG insights
            enhanced_recommendations = result.get("recommendations", [])
            if rag_context:
                enhanced_recommendations.extend([
                    f"Based on compliance documentation: {insight}"
                    for insight in rag_context.get("insights", [])
                ])
            
            return {
                "recommendations": enhanced_recommendations,
                "rag_context": rag_context
            }
            
        except Exception as e:
            logger.warning("RAG enhancement failed", error=str(e))
            return {}
    
    def _calculate_overall_score(self, test_results: List[TestResultResponse]) -> float:
        """Calculate overall compliance score."""
        
        if not test_results:
            return 0.0
        
        total_score = sum(result.score or 0 for result in test_results)
        return round(total_score / len(test_results), 2)
    
    async def _generate_recommendations(
        self,
        ai_system: AISystem,
        test_results: List[TestResultResponse],
        evaluator: BaseEvaluator
    ) -> List[str]:
        """Generate compliance recommendations."""
        
        recommendations = []
        
        # Collect recommendations from test results
        for result in test_results:
            if result.recommendations:
                recommendations.extend(result.recommendations)
        
        # Get evaluator-specific recommendations
        evaluator_recommendations = await evaluator.get_recommendations(ai_system, test_results)
        recommendations.extend(evaluator_recommendations)
        
        # Remove duplicates and return
        return list(set(recommendations))
    
    def _assess_risk_level(
        self,
        overall_score: float,
        test_results: List[TestResultResponse]
    ) -> RiskLevel:
        """Assess overall risk level based on scores and failures."""
        
        # Count critical failures
        critical_failures = sum(
            1 for result in test_results
            if not result.passed and (result.score or 0) < 30
        )
        
        # Assess based on score and critical failures
        if overall_score >= 90 and critical_failures == 0:
            return RiskLevel.LOW
        elif overall_score >= 70 and critical_failures <= 1:
            return RiskLevel.MEDIUM
        elif overall_score >= 50 and critical_failures <= 3:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    async def run_batch_tests(
        self,
        systems: List[AISystem],
        evaluator: BaseEvaluator,
        test_config: Dict[str, Any]
    ) -> List[ComplianceResult]:
        """Run compliance tests on multiple systems."""
        
        logger.info("Starting batch compliance evaluation", 
                   system_count=len(systems))
        
        # Run tests concurrently with limited concurrency
        semaphore = asyncio.Semaphore(test_config.get("max_concurrent", 3))
        
        async def evaluate_with_semaphore(system):
            async with semaphore:
                return await self.evaluate_system(system, evaluator, test_config)
        
        tasks = [evaluate_with_semaphore(system) for system in systems]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        compliance_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Batch test failed for system", 
                           system_id=systems[i].system_id, error=str(result))
                # Create failed result
                failed_result = ComplianceResult(
                    overall_score=0.0,
                    framework_compliance={},
                    test_results=[],
                    recommendations=[f"Evaluation failed: {str(result)}"],
                    risk_assessment=RiskLevel.CRITICAL
                )
                compliance_results.append(failed_result)
            else:
                compliance_results.append(result)
        
        logger.info("Batch compliance evaluation completed", 
                   system_count=len(systems),
                   successful=len([r for r in results if not isinstance(r, Exception)]))
        
        return compliance_results