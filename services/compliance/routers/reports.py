"""Compliance reporting endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
import structlog

from ...shared.database import db_manager
from ...shared.auth import get_current_active_user
from ...shared.models import ComplianceReport, AISystem, Test, TestResult
from ...shared.schemas import (
    UserResponse, ComplianceReportCreate, ComplianceReportResponse,
    ApiResponse, PaginatedResponse
)
from ...shared.exceptions import NotFoundError, ValidationError

logger = structlog.get_logger()
router = APIRouter()

@router.post("/", response_model=ApiResponse[ComplianceReportResponse])
async def create_compliance_report(
    report_data: ComplianceReportCreate,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Create a new compliance report."""
    
    # Verify AI system exists and belongs to user
    result = await db.execute(
        select(AISystem).where(
            AISystem.system_id == report_data.system_id,
            AISystem.user_id == current_user.user_id
        )
    )
    ai_system = result.scalar_one_or_none()
    
    if not ai_system:
        raise NotFoundError("AI System", report_data.system_id)
    
    # Create report record
    report = ComplianceReport(
        system_id=report_data.system_id,
        framework_id=report_data.framework_id,
        title=report_data.title,
        summary=report_data.summary,
        detailed_results=report_data.detailed_results,
        recommendations=report_data.recommendations,
        created_by=current_user.user_id
    )
    
    db.add(report)
    await db.commit()
    await db.refresh(report)
    
    # Generate detailed report in background
    background_tasks.add_task(
        generate_detailed_report,
        report.report_id
    )
    
    logger.info("Compliance report created", 
               report_id=report.report_id, 
               system_id=report_data.system_id,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=ComplianceReportResponse.model_validate(report),
        message="Compliance report created successfully"
    )

@router.get("/", response_model=ApiResponse[PaginatedResponse])
async def get_compliance_reports(
    system_id: Optional[int] = None,
    framework_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get compliance reports for the current user."""
    
    # Build query
    query = (
        select(ComplianceReport)
        .join(AISystem)
        .where(AISystem.user_id == current_user.user_id)
    )
    
    if system_id:
        query = query.where(ComplianceReport.system_id == system_id)
    if framework_id:
        query = query.where(ComplianceReport.framework_id == framework_id)
    if status:
        query = query.where(ComplianceReport.status == status)
    
    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(ComplianceReport.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    reports = result.scalars().all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    paginated_response = PaginatedResponse(
        items=[ComplianceReportResponse.model_validate(report) for report in reports],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )
    
    return ApiResponse(
        success=True,
        data=paginated_response
    )

@router.get("/{report_id}", response_model=ApiResponse[ComplianceReportResponse])
async def get_compliance_report(
    report_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get a specific compliance report."""
    
    result = await db.execute(
        select(ComplianceReport)
        .join(AISystem)
        .where(
            ComplianceReport.report_id == report_id,
            AISystem.user_id == current_user.user_id
        )
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise NotFoundError("Compliance Report", report_id)
    
    return ApiResponse(
        success=True,
        data=ComplianceReportResponse.model_validate(report)
    )

@router.put("/{report_id}/status", response_model=ApiResponse[ComplianceReportResponse])
async def update_report_status(
    report_id: int,
    status: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Update the status of a compliance report."""
    
    # Validate status
    valid_statuses = ["draft", "review", "approved", "published"]
    if status not in valid_statuses:
        raise ValidationError(
            f"Invalid status: {status}",
            details={"valid_statuses": valid_statuses}
        )
    
    # Get report
    result = await db.execute(
        select(ComplianceReport)
        .join(AISystem)
        .where(
            ComplianceReport.report_id == report_id,
            AISystem.user_id == current_user.user_id
        )
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise NotFoundError("Compliance Report", report_id)
    
    # Update status
    report.status = status
    await db.commit()
    await db.refresh(report)
    
    logger.info("Report status updated", 
               report_id=report_id, 
               new_status=status,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=ComplianceReportResponse.model_validate(report),
        message=f"Report status updated to {status}"
    )

@router.get("/analytics/summary", response_model=ApiResponse[dict])
async def get_compliance_analytics(
    days: int = 30,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get compliance analytics summary for the user's systems."""
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get user's AI systems
    systems_result = await db.execute(
        select(AISystem).where(AISystem.user_id == current_user.user_id)
    )
    user_systems = systems_result.scalars().all()
    system_ids = [s.system_id for s in user_systems]
    
    if not system_ids:
        return ApiResponse(
            success=True,
            data={
                "total_systems": 0,
                "total_reports": 0,
                "total_tests": 0,
                "average_compliance_score": 0.0,
                "reports_by_status": {},
                "tests_by_framework": {},
                "compliance_trends": []
            },
            message="No systems found for analytics"
        )
    
    # Get reports in date range
    reports_result = await db.execute(
        select(ComplianceReport).where(
            and_(
                ComplianceReport.system_id.in_(system_ids),
                ComplianceReport.created_at >= start_date,
                ComplianceReport.created_at <= end_date
            )
        )
    )
    reports = reports_result.scalars().all()
    
    # Get tests in date range
    tests_result = await db.execute(
        select(Test).where(
            and_(
                Test.system_id.in_(system_ids),
                Test.created_at >= start_date,
                Test.created_at <= end_date
            )
        )
    )
    tests = tests_result.scalars().all()
    
    # Get test results for compliance scores
    test_ids = [t.test_id for t in tests]
    if test_ids:
        results_result = await db.execute(
            select(TestResult).where(TestResult.test_id.in_(test_ids))
        )
        test_results = results_result.scalars().all()
    else:
        test_results = []
    
    # Calculate analytics
    reports_by_status = {}
    for report in reports:
        status = report.status
        reports_by_status[status] = reports_by_status.get(status, 0) + 1
    
    # Calculate average compliance score
    scores = [r.score for r in test_results if r.score is not None]
    average_score = sum(scores) / len(scores) if scores else 0.0
    
    # Group tests by framework (simplified)
    tests_by_framework = {}
    for test in tests:
        # In a real implementation, you'd get framework from test configuration
        framework = "GDPR"  # Placeholder
        tests_by_framework[framework] = tests_by_framework.get(framework, 0) + 1
    
    analytics = {
        "period_days": days,
        "total_systems": len(user_systems),
        "total_reports": len(reports),
        "total_tests": len(tests),
        "total_test_results": len(test_results),
        "average_compliance_score": round(average_score, 2),
        "reports_by_status": reports_by_status,
        "tests_by_framework": tests_by_framework,
        "compliance_trends": [
            {
                "date": (start_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                "score": round(average_score + (i % 10 - 5), 2)  # Mock trend data
            }
            for i in range(0, days, max(1, days // 10))
        ]
    }
    
    return ApiResponse(
        success=True,
        data=analytics,
        message=f"Analytics for the last {days} days"
    )

async def generate_detailed_report(report_id: int):
    """Background task to generate detailed compliance report."""
    
    async with db_manager.get_session() as db:
        try:
            # Get report
            result = await db.execute(
                select(ComplianceReport).where(ComplianceReport.report_id == report_id)
            )
            report = result.scalar_one_or_none()
            
            if not report:
                logger.error("Report not found for detailed generation", report_id=report_id)
                return
            
            # Get AI system
            system_result = await db.execute(
                select(AISystem).where(AISystem.system_id == report.system_id)
            )
            ai_system = system_result.scalar_one_or_none()
            
            if not ai_system:
                logger.error("AI system not found", system_id=report.system_id)
                return
            
            # Get recent test results for this system
            tests_result = await db.execute(
                select(Test).where(
                    and_(
                        Test.system_id == report.system_id,
                        Test.status == "completed"
                    )
                ).order_by(Test.created_at.desc()).limit(10)
            )
            recent_tests = tests_result.scalars().all()
            
            # Aggregate test results
            all_test_results = []
            for test in recent_tests:
                results_result = await db.execute(
                    select(TestResult).where(TestResult.test_id == test.test_id)
                )
                test_results = results_result.scalars().all()
                all_test_results.extend(test_results)
            
            # Generate enhanced summary
            total_tests = len(all_test_results)
            passed_tests = len([r for r in all_test_results if r.passed])
            average_score = sum(r.score or 0 for r in all_test_results) / total_tests if total_tests > 0 else 0
            
            enhanced_summary = {
                "system_name": ai_system.name,
                "system_type": ai_system.system_type,
                "total_tests_analyzed": total_tests,
                "tests_passed": passed_tests,
                "tests_failed": total_tests - passed_tests,
                "pass_rate": round((passed_tests / total_tests) * 100, 2) if total_tests > 0 else 0,
                "average_compliance_score": round(average_score, 2),
                "compliance_frameworks": ai_system.compliance_frameworks or [],
                "generation_timestamp": datetime.utcnow().isoformat()
            }
            
            # Generate detailed recommendations
            detailed_recommendations = {
                "immediate_actions": [],
                "medium_term_improvements": [],
                "long_term_strategies": []
            }
            
            if average_score < 60:
                detailed_recommendations["immediate_actions"].extend([
                    "Address critical compliance failures immediately",
                    "Review and update system documentation",
                    "Implement basic security measures"
                ])
            elif average_score < 80:
                detailed_recommendations["medium_term_improvements"].extend([
                    "Enhance existing compliance measures",
                    "Implement additional monitoring",
                    "Conduct regular compliance reviews"
                ])
            else:
                detailed_recommendations["long_term_strategies"].extend([
                    "Maintain current compliance standards",
                    "Consider advanced compliance features",
                    "Share best practices with other systems"
                ])
            
            # Update report with enhanced data
            report.summary = enhanced_summary
            report.detailed_results = {
                "test_breakdown": [
                    {
                        "test_id": r.test_id,
                        "score": r.score,
                        "passed": r.passed,
                        "details": r.details
                    }
                    for r in all_test_results
                ],
                "compliance_areas": {
                    "data_protection": round(average_score * 0.9, 2),
                    "security": round(average_score * 1.1, 2),
                    "transparency": round(average_score * 0.95, 2)
                }
            }
            report.recommendations = detailed_recommendations
            report.status = "review"
            
            await db.commit()
            
            logger.info("Detailed report generated successfully", 
                       report_id=report_id,
                       total_tests=total_tests,
                       average_score=average_score)
            
        except Exception as e:
            logger.error("Failed to generate detailed report", 
                        report_id=report_id, error=str(e))