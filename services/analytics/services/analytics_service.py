"""Core analytics service for AI compliance platform."""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import structlog
from sqlalchemy import text, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.database import db_manager
from ...shared.redis_client import redis_client
from ...shared.models import TestResult, AISystem, User
from ...shared.exceptions import PlatformError

logger = structlog.get_logger()

class AnalyticsService:
    """Core analytics service for generating insights and reports."""
    
    def __init__(self):
        self.cache_ttl = 300  # 5 minutes cache
        
    async def initialize(self):
        """Initialize the analytics service."""
        logger.info("Initializing analytics service")
        
    async def close(self):
        """Close the analytics service."""
        logger.info("Closing analytics service")
        
    async def get_dashboard_metrics(self, user_id: int, time_range: str = "7d") -> Dict[str, Any]:
        """Get dashboard metrics for a user."""
        cache_key = f"dashboard_metrics:{user_id}:{time_range}"
        
        # Try cache first
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
            
        async with db_manager.get_session() as session:
            # Calculate date range
            end_date = datetime.utcnow()
            if time_range == "24h":
                start_date = end_date - timedelta(hours=24)
            elif time_range == "7d":
                start_date = end_date - timedelta(days=7)
            elif time_range == "30d":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=7)
                
            # Get basic metrics
            total_tests = await self._get_total_tests(session, user_id, start_date, end_date)
            total_systems = await self._get_total_systems(session, user_id)
            total_models = await self._get_total_models(session, user_id)
            avg_compliance_score = await self._get_avg_compliance_score(session, user_id, start_date, end_date)
            
            # Get trend data
            test_trends = await self._get_test_trends(session, user_id, start_date, end_date)
            compliance_trends = await self._get_compliance_trends(session, user_id, start_date, end_date)
            
            # Get top issues
            top_issues = await self._get_top_issues(session, user_id, start_date, end_date)
            
            metrics = {
                "summary": {
                    "total_tests": total_tests,
                    "total_systems": total_systems,
                    "total_models": total_models,
                    "avg_compliance_score": avg_compliance_score
                },
                "trends": {
                    "tests": test_trends,
                    "compliance": compliance_trends
                },
                "top_issues": top_issues,
                "time_range": time_range,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Cache results
            await redis_client.setex(cache_key, self.cache_ttl, json.dumps(metrics, default=str))
            
            return metrics
            
    async def get_compliance_report(self, user_id: int, system_id: Optional[int] = None, 
                                  time_range: str = "30d") -> Dict[str, Any]:
        """Generate comprehensive compliance report."""
        async with db_manager.get_session() as session:
            # Calculate date range
            end_date = datetime.utcnow()
            if time_range == "7d":
                start_date = end_date - timedelta(days=7)
            elif time_range == "30d":
                start_date = end_date - timedelta(days=30)
            elif time_range == "90d":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=30)
                
            # Build base query
            query = session.query(TestResult).filter(
                TestResult.created_at >= start_date,
                TestResult.created_at <= end_date
            )
            
            # Filter by system if specified
            if system_id:
                query = query.join(Model).join(AISystem).filter(AISystem.id == system_id)
            else:
                query = query.join(Model).join(AISystem).filter(AISystem.user_id == user_id)
                
            results = await query.all()
            
            # Analyze results
            total_tests = len(results)
            passed_tests = len([r for r in results if r.overall_score >= 0.7])
            failed_tests = total_tests - passed_tests
            
            # Calculate compliance by category
            compliance_by_category = {}
            risk_levels = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            
            for result in results:
                if result.results:
                    for category, data in result.results.items():
                        if category not in compliance_by_category:
                            compliance_by_category[category] = []
                        compliance_by_category[category].append(data.get("score", 0))
                        
                        # Count risk levels
                        risk = data.get("risk_level", "medium")
                        if risk in risk_levels:
                            risk_levels[risk] += 1
                            
            # Calculate averages
            avg_by_category = {}
            for category, scores in compliance_by_category.items():
                avg_by_category[category] = sum(scores) / len(scores) if scores else 0
                
            report = {
                "summary": {
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "pass_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                    "overall_compliance_score": sum(avg_by_category.values()) / len(avg_by_category) if avg_by_category else 0
                },
                "compliance_by_category": avg_by_category,
                "risk_distribution": risk_levels,
                "time_range": time_range,
                "system_id": system_id,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return report
            
    async def get_test_analytics(self, user_id: int, test_id: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed test analytics."""
        async with db_manager.get_session() as session:
            query = session.query(TestResult)
            
            if test_id:
                query = query.filter(TestResult.id == test_id)
            else:
                # Get tests for user's systems
                query = query.join(Model).join(AISystem).filter(AISystem.user_id == user_id)
                
            results = await query.all()
            
            if not results:
                raise PlatformError("No test results found", "NOT_FOUND", 404)
                
            # Analyze performance over time
            performance_timeline = []
            for result in sorted(results, key=lambda x: x.created_at):
                performance_timeline.append({
                    "timestamp": result.created_at.isoformat(),
                    "overall_score": result.overall_score,
                    "test_id": result.id
                })
                
            # Calculate statistics
            scores = [r.overall_score for r in results if r.overall_score is not None]
            
            analytics = {
                "total_tests": len(results),
                "performance_stats": {
                    "average_score": sum(scores) / len(scores) if scores else 0,
                    "min_score": min(scores) if scores else 0,
                    "max_score": max(scores) if scores else 0,
                    "latest_score": scores[-1] if scores else 0
                },
                "performance_timeline": performance_timeline,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return analytics
            
    async def _get_total_tests(self, session: AsyncSession, user_id: int, 
                             start_date: datetime, end_date: datetime) -> int:
        """Get total number of tests for user in date range."""
        result = await session.execute(
            text("""
                SELECT COUNT(*) 
                FROM test_results tr
                JOIN models m ON tr.model_id = m.id
                JOIN ai_systems s ON m.system_id = s.id
                WHERE s.user_id = :user_id 
                AND tr.created_at >= :start_date 
                AND tr.created_at <= :end_date
            """),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date}
        )
        return result.scalar() or 0
        
    async def _get_total_systems(self, session: AsyncSession, user_id: int) -> int:
        """Get total number of systems for user."""
        result = await session.execute(
            text("SELECT COUNT(*) FROM ai_systems WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        return result.scalar() or 0
        
    async def _get_total_models(self, session: AsyncSession, user_id: int) -> int:
        """Get total number of models for user."""
        result = await session.execute(
            text("""
                SELECT COUNT(*) 
                FROM models m
                JOIN ai_systems s ON m.system_id = s.id
                WHERE s.user_id = :user_id
            """),
            {"user_id": user_id}
        )
        return result.scalar() or 0
        
    async def _get_avg_compliance_score(self, session: AsyncSession, user_id: int,
                                      start_date: datetime, end_date: datetime) -> float:
        """Get average compliance score for user in date range."""
        result = await session.execute(
            text("""
                SELECT AVG(tr.overall_score) 
                FROM test_results tr
                JOIN models m ON tr.model_id = m.id
                JOIN ai_systems s ON m.system_id = s.id
                WHERE s.user_id = :user_id 
                AND tr.created_at >= :start_date 
                AND tr.created_at <= :end_date
                AND tr.overall_score IS NOT NULL
            """),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date}
        )
        return float(result.scalar() or 0)
        
    async def _get_test_trends(self, session: AsyncSession, user_id: int,
                             start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get test execution trends over time."""
        result = await session.execute(
            text("""
                SELECT DATE(tr.created_at) as test_date, COUNT(*) as test_count
                FROM test_results tr
                JOIN models m ON tr.model_id = m.id
                JOIN ai_systems s ON m.system_id = s.id
                WHERE s.user_id = :user_id 
                AND tr.created_at >= :start_date 
                AND tr.created_at <= :end_date
                GROUP BY DATE(tr.created_at)
                ORDER BY test_date
            """),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date}
        )
        
        return [{"date": str(row[0]), "count": row[1]} for row in result.fetchall()]
        
    async def _get_compliance_trends(self, session: AsyncSession, user_id: int,
                                   start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get compliance score trends over time."""
        result = await session.execute(
            text("""
                SELECT DATE(tr.created_at) as test_date, AVG(tr.overall_score) as avg_score
                FROM test_results tr
                JOIN models m ON tr.model_id = m.id
                JOIN ai_systems s ON m.system_id = s.id
                WHERE s.user_id = :user_id 
                AND tr.created_at >= :start_date 
                AND tr.created_at <= :end_date
                AND tr.overall_score IS NOT NULL
                GROUP BY DATE(tr.created_at)
                ORDER BY test_date
            """),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date}
        )
        
        return [{"date": str(row[0]), "score": float(row[1])} for row in result.fetchall()]
        
    async def _get_top_issues(self, session: AsyncSession, user_id: int,
                            start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get top compliance issues."""
        # This is a simplified implementation - in reality you'd analyze the test results
        # to identify common failure patterns
        return [
            {"issue": "PII Detection Failures", "count": 15, "severity": "high"},
            {"issue": "Bias in Responses", "count": 8, "severity": "medium"},
            {"issue": "Hallucination Detected", "count": 12, "severity": "high"},
            {"issue": "EU AI Act Violations", "count": 5, "severity": "critical"}
        ]

# Global instance
analytics_service = AnalyticsService()