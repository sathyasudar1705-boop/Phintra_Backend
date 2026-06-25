from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any

from uuid import UUID
from app.database import get_db
from app.models.employee import Employee, EmployeeActivityEvent
from app.models.company import Company
from app.models.department import Department
from app.models.training import TrainingCompletion, TrainingModule
from app.models.reported_email import ReportedEmail
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])

@router.get("")
def get_company_leaderboard(
    skip: int = Query(0, ge=0),
    limit: int = Query(9999, ge=1, le=9999),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve the live company leaderboard for the current user's organization."""
    # Find company_id depending on current user role
    company_id = None
    viewer_employee_id = None

    if current_user.role == "Employee" or current_user.role == "employee":
        emp = db.query(Employee).filter(Employee.id == current_user.id).first()
        if not emp:
            emp = db.query(Employee).filter(Employee.email == current_user.email).first()
        
        if emp:
            company_id = emp.company_id
            viewer_employee_id = emp.id
    else:
        # User is Admin or Manager
        company = db.query(Company).filter(Company.admin_id == current_user.id).first()
        if company:
            company_id = company.id

    if not company_id:
        return {
            "leaderboard": [],
            "total_count": 0,
            "viewer_stats": None
        }

    # 1. Total training modules in the company's admin scope (to calculate completion %)
    admin_id = db.query(Company.admin_id).filter(Company.id == company_id).scalar()
    total_modules = db.query(TrainingModule).filter(TrainingModule.admin_id == admin_id).count() if admin_id else 0

    # 2. Build subqueries for completions, reports, and rewards to do efficient joined aggregation
    completed_sub = db.query(
        TrainingCompletion.employee_id,
        func.count(TrainingCompletion.id).label("completed_count")
    ).filter(
        TrainingCompletion.status == "completed"
    ).group_by(TrainingCompletion.employee_id).subquery()

    reports_sub = db.query(
        ReportedEmail.employee_id,
        func.count(ReportedEmail.id).label("reports_count")
    ).group_by(ReportedEmail.employee_id).subquery()

    rewards_sub = db.query(
        EmployeeActivityEvent.employee_id,
        func.sum(EmployeeActivityEvent.points_change).label("total_xp")
    ).group_by(EmployeeActivityEvent.employee_id).subquery()

    # 3. Join everything in a single SQL query
    query = db.query(
        Employee,
        func.coalesce(completed_sub.c.completed_count, 0).label("completed_count"),
        func.coalesce(reports_sub.c.reports_count, 0).label("reports_count"),
        func.coalesce(rewards_sub.c.total_xp, 0).label("total_xp")
    ).outerjoin(
        completed_sub, Employee.id == completed_sub.c.employee_id
    ).outerjoin(
        reports_sub, Employee.id == reports_sub.c.employee_id
    ).outerjoin(
        rewards_sub, Employee.id == rewards_sub.c.employee_id
    ).filter(
        Employee.company_id == company_id,
        Employee.is_active == True
    )

    all_results = query.all()
    total_employees = len(all_results)

    # 4. Process metrics and sort in memory to calculate exact rank and percentile
    processed_list = []
    for row in all_results:
        emp = row[0]
        completed_count = row[1]
        reports_count = row[2]
        total_xp = int(row[3]) if row[3] else 0

        # Calculate security score (100 - risk_score)
        security_score = round(100.0 - emp.risk_score, 1)

        # Calculate training completion percentage
        completion_percentage = int((completed_count / total_modules) * 100) if total_modules > 0 else 0

        processed_list.append({
            "employee_id": str(emp.id),
            "name": emp.name or f"{emp.first_name} {emp.last_name}".strip() or "Employee",
            "email": emp.email,
            "department_id": str(emp.department_id),
            "security_score": security_score,
            "completion_percentage": completion_percentage,
            "reports_count": reports_count,
            "total_xp": total_xp,
            "risk_score": emp.risk_score
        })

    # Sort rules:
    # 1. Security Score (descending)
    # 2. Total XP (descending)
    # 3. Training Completion % (descending)
    # 4. Reports Count (descending)
    processed_list.sort(
        key=lambda x: (x["security_score"], x["total_xp"], x["completion_percentage"], x["reports_count"]),
        reverse=True
    )

    # 5. Enrich with ranks and percentiles, and fetch department names
    viewer_stats = None
    final_leaderboard = []

    # Pre-fetch department names to avoid N+1 queries
    departments = {d.id: d.name for d in db.query(Department).all()}

    for index, item in enumerate(processed_list):
        rank = index + 1
        percentile = round(((total_employees - rank + 1) / total_employees) * 100) if total_employees > 0 else 100
        
        item["rank"] = rank
        item["percentile"] = percentile
        item["department"] = departments.get(UUID(item["department_id"]), "General")
        
        # Hardcode some nice decorative badges based on achievements to match dummyData
        badges = []
        if item["security_score"] >= 90:
            badges.append("Security Champion")
        if item["reports_count"] >= 3:
            badges.append("Top Reporter")
        if item["total_xp"] >= 500:
            badges.append("Perfect Month")
        item["badges"] = badges

        if viewer_employee_id and UUID(item["employee_id"]) == viewer_employee_id:
            viewer_stats = {
                "rank": rank,
                "percentile": percentile,
                "security_score": item["security_score"],
                "total_xp": item["total_xp"],
                "completion_percentage": item["completion_percentage"],
                "reports_count": item["reports_count"]
            }

        final_leaderboard.append(item)

    # Paginate
    paginated_list = final_leaderboard[skip:skip+limit]

    return {
        "leaderboard": paginated_list,
        "total_count": total_employees,
        "viewer_stats": viewer_stats
    }


@router.get("/employee", response_model=List[Dict[str, Any]])
def get_employee_leaderboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve the scoped leaderboard for employees belonging to the same company or admin."""
    from app.models.quiz import QuizAttempt
    
    # Retrieve the current employee record using the logged-in user id
    current_employee = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not current_employee:
        # Fallback if lookup by ID fails: check by email
        current_employee = db.query(Employee).filter(Employee.email == current_user.email).first()

    if not current_employee:
        raise HTTPException(
            status_code=404,
            detail="Employee record not found for the authenticated user."
        )

    # Scoping logic:
    # Query all active employees globally to show all employees in the leaderboard
    employees = db.query(Employee).filter(
        Employee.is_active == True
    ).all()

    # Pre-fetch departments and companies
    departments = {d.id: d.name for d in db.query(Department).all()}
    companies = {c.id: c.company_name for c in db.query(Company).all()}

    processed_list = []
    for emp in employees:
        # Compute real statistics from database tables
        # 1. Total Points / XP from employee_activity_events points_change
        total_points = db.query(func.sum(EmployeeActivityEvent.points_change)).filter(
            EmployeeActivityEvent.employee_id == emp.id
        ).scalar() or 0

        # 2. Total report count
        report_count = db.query(ReportedEmail).filter(
            ReportedEmail.employee_id == emp.id
        ).count()

        # 3. Safe report count (Simulation campaigns or validated suspicious/phish reports)
        safe_report_count = db.query(ReportedEmail).filter(
            ReportedEmail.employee_id == emp.id,
            (ReportedEmail.campaign_id.isnot(None)) | (ReportedEmail.report_status.in_(["Verified Phish", "Suspicious"]))
        ).count()

        # 4. Training completed count
        training_completed_count = db.query(TrainingCompletion).filter(
            TrainingCompletion.employee_id == emp.id,
            TrainingCompletion.status == "completed"
        ).count()

        # 5. Quiz pass count
        quiz_pass_count = db.query(QuizAttempt.quiz_id).filter(
            QuizAttempt.employee_id == emp.id,
            QuizAttempt.passed == True
        ).distinct().count()

        # Determine best badge
        security_score = round(100.0 - emp.risk_score, 1)
        badge = "Active Agent"
        if security_score >= 90:
            badge = "Security Champion"
        elif safe_report_count >= 3:
            badge = "Top Reporter"
        elif total_points >= 500:
            badge = "Perfect Month"

        processed_list.append({
            "employee_id": str(emp.id),
            "employee_name": emp.name or f"{emp.first_name or ''} {emp.last_name or ''}".strip() or "Employee",
            "email": emp.email,
            "department": departments.get(emp.department_id, "General"),
            "company": companies.get(emp.company_id, "No Company"),
            "total_points": int(total_points),
            "risk_score": emp.risk_score,
            "report_count": report_count,
            "safe_report_count": safe_report_count,
            "training_completed_count": training_completed_count,
            "quiz_pass_count": quiz_pass_count,
            "badge": badge,
            "security_score": security_score
        })

    # Sorting rules:
    # 1. Total points (descending)
    # 2. Safe report count (descending)
    # 3. Training completed count (descending)
    # 4. Quiz pass count (descending)
    # 5. Risk score (ascending, meaning lower risk is better)
    processed_list.sort(
        key=lambda x: (
            x["total_points"],
            x["safe_report_count"],
            x["training_completed_count"],
            x["quiz_pass_count"],
            -x["risk_score"]
        ),
        reverse=True
    )

    # Assign ranks
    for index, item in enumerate(processed_list):
        item["rank"] = index + 1

    return processed_list
