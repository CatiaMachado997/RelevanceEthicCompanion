"""
ESL Transparency API Routes

Critical for trust: Users can see ALL ESL decisions and reasoning.
No hidden behavior, complete transparency.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel, Field

from services.orchestrator_v2 import OrchestratorV2
from services.context_manager import ContextManager
from esl.audit import ESLAuditLogger
from utils.db import get_db
from utils.supabase_auth import get_current_read_user_id


# Response models
class ESLLog(BaseModel):
    """Single ESL audit log entry"""
    id: str
    timestamp: str
    action_type: str
    decision_status: str
    decision_reason: str
    violated_values: list
    applied_rules: list
    confidence: float


class ESLLogsResponse(BaseModel):
    """Response with ESL logs"""
    user_id: str
    logs: list
    total_count: int
    filtered_count: int


class ESLReportResponse(BaseModel):
    """ESL transparency report"""
    user_id: str
    period_days: int
    total_decisions: int
    approved_count: int
    vetoed_count: int
    modified_count: int
    approval_rate: float
    recent_vetoes: list
    message: Optional[str] = None


# Router
router = APIRouter(prefix="/api/transparency", tags=["ESL Transparency"])


# Dependencies
def get_audit_logger() -> ESLAuditLogger:
    """Get ESLAuditLogger instance"""
    return ESLAuditLogger()

def get_orchestrator() -> OrchestratorV2:
    """Get OrchestratorV2 instance"""
    context_manager = ContextManager()
    return OrchestratorV2(context_manager)


@router.get("/logs", response_model=ESLLogsResponse)
async def get_esl_logs(
    user_id: str = Depends(get_current_read_user_id),
    days: int = 7,
    decision_status: Optional[str] = None,
    limit: int = 100,
    audit_logger: ESLAuditLogger = Depends(get_audit_logger)
):
    """
    Get ESL audit logs for the user (in-memory)
    """
    try:
        logs = await audit_logger.get_user_logs(
            user_id=user_id,
            days=days,
            status_filter=decision_status
        )
        
        # Manually apply limit for now, as get_user_logs does not support limit/offset directly
        # TODO: Enhance ESLAuditLogger.get_user_logs to support limit/offset
        limited_logs = logs[:limit]

        return {
            "user_id": str(user_id),
            "logs": [log.model_dump() for log in limited_logs], # Convert Pydantic models to dicts
            "total_count": len(logs), # Total available before limit
            "filtered_count": len(limited_logs)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching ESL logs: {str(e)}"
        )


@router.get("/report", response_model=dict)
async def get_esl_report(
    user_id: str = Depends(get_current_read_user_id),
    days: int = 7,
    orchestrator: OrchestratorV2 = Depends(get_orchestrator)
):
    """
    Get comprehensive ESL transparency report

    Shows:
    - Total decisions made
    - Approval rate
    - How many actions were blocked/modified
    - Which values were most protected
    - Recent examples of ESL protecting the user

    Args:
        user_id: Current user ID
        days: Number of days to include in report
        orchestrator: OrchestratorV2 instance
    
    Returns:
        Transparency report
        
    Example:
        GET /api/transparency/report?days=30
        
        Response:
        {
            "user_id": "...",
            "period_days": 30,
            "total_decisions": 45,
            "approved_count": 40,
            "vetoed_count": 3,
            "modified_count": 2,
            "approval_rate": 0.889,
            "recent_vetoes": [...]
        }
    """
    try:
        report = await orchestrator.get_esl_transparency_report(
            user_id=user_id,
            days=days
        )
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report: {str(e)}"
        )


@router.get("/stats", response_model=dict)
async def get_esl_statistics(
    user_id: str = Depends(get_current_read_user_id),
    audit_logger: ESLAuditLogger = Depends(get_audit_logger)
):
    """
    Get ESL statistics and insights (in-memory)
    """
    try:
        stats = await audit_logger.get_statistics(user_id=str(user_id))
        return stats

        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating statistics: {str(e)}"
        )


@router.get("/insights", response_model=dict)
async def get_esl_insights(
    user_id: str = Depends(get_current_read_user_id),
    audit_logger: ESLAuditLogger = Depends(get_audit_logger)
):
    """
    Get personalized insights about ESL protection (in-memory)
    """
    try:
        logs = await audit_logger.get_user_logs(user_id=str(user_id), days=7)

        if not logs:
            return {
                "user_id": str(user_id),
                "insights": [
                    "No ESL activity in the last 7 days."
                ]
            }
        
        # Generate insights
        insights = []
        
        vetoed_count = sum(1 for log in logs if log.decision.status.value == "VETOED")
        if vetoed_count > 0:
            insights.append(
                f"🛡️ ESL protected you by blocking {vetoed_count} action(s) this week"
            )
        
        modified_count = sum(1 for log in logs if log.decision.status.value == "MODIFIED")
        if modified_count > 0:
            insights.append(
                f"✏️ ESL modified {modified_count} action(s) to align with your values"
            )
        
        approved_count = sum(1 for log in logs if log.decision.status.value == "APPROVED")
        total = len(logs)
        approval_rate = (approved_count / total) * 100 if total > 0 else 0
        
        insights.append(
            f"✅ {approval_rate:.0f}% of actions were ethical and approved"
        )
        
        # Value-specific insights
        violated_values = []
        for log in logs:
            if log.decision.violated_values:
                violated_values.extend(log.decision.violated_values)
        
        if violated_values:
            from collections import Counter
            most_common = Counter(violated_values).most_common(1)[0]
            insights.append(
                f"🎯 Your '{most_common[0]}' boundary was protected {most_common[1]} time(s)"
            )
        
        return {
            "user_id": str(user_id),
            "period": "Last 7 days",
            "insights": insights
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating insights: {str(e)}"
        )
