from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.analytics_service import (
    get_dashboard_analytics, get_department_analytics,
    get_security_scores_trend, get_training_completion_stats,
    get_ai_predictive_insights, get_insights_analytics
)
from app.utils.dependencies import require_manager
from app.models.user import User
from app.models.employee import Employee

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard")
def get_dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve global platform statistics summary (Managers & Admins)."""
    return get_dashboard_analytics(db)

@router.get("/departments")
def get_department_summary(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve comparative department risk parameters and metrics (Managers & Admins)."""
    return get_department_analytics(db)

@router.get("/department-scores")
def get_department_scores_analytics(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Alias for comparative department risk parameters (Managers & Admins)."""
    return get_department_analytics(db)

@router.get("/employee-scores")
def get_employee_scores_analytics(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve individual employee risk ratings list (Managers & Admins)."""
    employees = db.query(Employee).all()
    return [{
        "employee_id": str(e.id),
        "name": f"{e.first_name} {e.last_name}",
        "email": e.email,
        "risk_score": e.risk_score,
        "status": e.status
    } for e in employees]

@router.get("/security-scores")
def get_security_scores_history(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve security rating tracking score trend timeline (Managers & Admins)."""
    return get_security_scores_trend(db)

@router.get("/trends")
def get_security_trends_analytics(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Alias for security rating tracking score trend timeline (Managers & Admins)."""
    return get_security_scores_trend(db)

@router.get("/training-completion")
def get_training_module_stats(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve course catalog training modules completion statistics (Managers & Admins)."""
    return get_training_completion_stats(db)

@router.get("/ai-insights")
def get_ai_insights(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve heuristic gaps and AI-generated mitigation instructions (Managers & Admins)."""
    return get_ai_predictive_insights(db)

@router.get("/insights")
def get_insights_analytics_endpoint(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve database-backed insights analytics (Managers & Admins)."""
    return get_insights_analytics(db)
