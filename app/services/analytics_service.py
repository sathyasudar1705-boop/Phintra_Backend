from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.employee import Employee
from app.models.department import Department
from app.models.campaign import Campaign, CampaignRecipient
from app.models.training import TrainingModule, TrainingAssignment
from app.models.quiz import QuizAttempt
from app.models.certificate import Certificate
from app.models.audit_log import SecurityScore

def get_dashboard_analytics(db: Session) -> dict:
    """Retrieve global analytics indices."""
    total_employees = db.query(Employee).count()
    total_departments = db.query(Department).count()
    total_campaigns = db.query(Campaign).count()
    active_campaigns = db.query(Campaign).filter(Campaign.status == "Active").count()
    total_modules = db.query(TrainingModule).count()
    
    # Calculate avg corporate risk rating
    avg_risk = db.query(func.avg(Employee.risk_score)).scalar() or 0.0
    avg_score = max(0.0, 100.0 - float(avg_risk))

    return {
        "total_employees": total_employees,
        "total_departments": total_departments,
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_modules": total_modules,
        "average_security_score": round(avg_score, 1)
    }

def get_department_analytics(db: Session) -> list:
    """Retrieve comparative metrics grouped by department."""
    departments = db.query(Department).all()
    results = []
    
    for dept in departments:
        # Get headcount
        employees = db.query(Employee).filter(Employee.department_id == dept.id).all()
        headcount = len(employees)
        
        # Get average risk score
        avg_risk = 0.0
        if headcount > 0:
            avg_risk = sum(e.risk_score for e in employees) / headcount
            
        # Get completion rate of assignments
        total_assignments = 0
        completed_assignments = 0
        for emp in employees:
            assigns = db.query(TrainingAssignment).filter(TrainingAssignment.employee_id == emp.id).all()
            total_assignments += len(assigns)
            completed_assignments += sum(1 for a in assigns if a.completed)
            
        completion_rate = 0.0
        if total_assignments > 0:
            completion_rate = (completed_assignments / total_assignments) * 100.0
            
        results.append({
            "department_id": str(dept.id),
            "department_name": dept.name,
            "headcount": headcount,
            "avg_risk_score": round(avg_risk, 1),
            "security_score": round(100.0 - avg_risk, 1),
            "training_completion_rate": round(completion_rate, 1)
        })
        
    return results

def get_security_scores_trend(db: Session) -> list:
    """Retrieve recent aggregated security scores over time."""
    scores = db.query(SecurityScore).order_by(SecurityScore.recorded_at.asc()).limit(50).all()
    return [
        {
            "id": str(s.id),
            "score": s.score,
            "recorded_at": s.recorded_at.isoformat()
        } for s in scores
    ]

def get_training_completion_stats(db: Session) -> list:
    """Retrieve completion details grouped by training module."""
    modules = db.query(TrainingModule).all()
    results = []
    for mod in modules:
        total_assigned = db.query(TrainingAssignment).filter(TrainingAssignment.module_id == mod.id).count()
        completed = db.query(TrainingAssignment).filter(TrainingAssignment.module_id == mod.id, TrainingAssignment.completed == True).count()
        results.append({
            "module_id": str(mod.id),
            "module_title": mod.title,
            "total_assigned": total_assigned,
            "completed": completed,
            "completion_rate": round((completed / total_assigned * 100.0), 1) if total_assigned > 0 else 0.0
        })
    return results

def get_ai_predictive_insights(db: Session) -> dict:
    """Compute risk gaps and generate actionable mitigation tips."""
    # Find departments with highest avg risk rating
    dept_stats = get_department_analytics(db)
    high_risk_depts = sorted(dept_stats, key=lambda x: x["avg_risk_score"], reverse=True)
    
    primary_threat_vector = "Spear Phishing"
    risk_summary = []
    mitigations = []
    
    if high_risk_depts:
        top_risk = high_risk_depts[0]
        if top_risk["avg_risk_score"] > 50.0:
            risk_summary.append(f"Critical Gap: Low Phishing Literacy in {top_risk['department_name']}")
            mitigations.append(f"Auto-schedule a targeted spear phishing simulation focusing on {top_risk['department_name']} roles.")
            
    # Count MFA exemptions (e.g. users or employees with high risk rating due to course incompleteness)
    high_risk_count = db.query(Employee).filter(Employee.risk_score >= 60.0).count()
    if high_risk_count > 0:
        risk_summary.append(f"Active risk threat: {high_risk_count} employees showing risk index >= 60%")
        mitigations.append(f"Auto-enroll the {high_risk_count} flagged employees into mandatory Password Hygiene refresher modules.")
        
    if not risk_summary:
        risk_summary.append("Low general threat profile detected.")
        mitigations.append("Maintain recurring simulation runs quarterly to keep vigilance high.")
        
    return {
        "primary_threat_vector": primary_threat_vector,
        "gaps_identified": risk_summary,
        "suggested_mitigations": mitigations
    }
