from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.employee import Employee, EmployeeActivityEvent
from app.models.department import Department
from app.models.campaign import Campaign, CampaignRecipient, CampaignClick
from app.models.training import TrainingModule, TrainingAssignment, TrainingCompletion
from app.models.quiz import QuizAttempt
from app.models.certificate import Certificate
from app.models.reported_email import ReportedEmail
from app.models.audit_log import SecurityScore
from app.models.company import Company
from app.models.email_log import EmailLog
from typing import Optional
import uuid as _uuid


def _resolve_scope(db: Session, admin_id=None, company_id=None):
    """Ensure both admin_id and company_id are populated if either is available."""
    if admin_id and not company_id:
        comp = db.query(Company).filter(Company.admin_id == admin_id).first()
        if comp:
            company_id = comp.id
    elif company_id and not admin_id:
        comp = db.query(Company).filter(Company.id == company_id).first()
        if comp:
            admin_id = comp.admin_id
    return admin_id, company_id


def _employee_filter(db: Session, admin_id=None, company_id=None):
    """Return a base Employee query filtered to the tenant scope."""
    q = db.query(Employee)
    if company_id:
        q = q.filter(Employee.company_id == company_id)
    elif admin_id:
        q = q.filter(Employee.admin_id == admin_id)
    return q


def get_dashboard_analytics(db: Session, admin_id=None, company_id=None) -> dict:
    """Retrieve platform statistics summary scoped to the given tenant."""
    admin_id, company_id = _resolve_scope(db, admin_id, company_id)

    emp_q = _employee_filter(db, admin_id, company_id)
    total_employees = emp_q.count()
    emp_ids = [e.id for e in emp_q.all()]

    total_departments = db.query(Department).filter(
        Department.company_id == company_id if company_id else True
    ).count() if company_id else db.query(Department).count()

    # Count campaigns owned by this admin
    if admin_id:
        total_campaigns = db.query(Campaign).filter(Campaign.admin_id == admin_id).count()
        active_campaigns = db.query(Campaign).filter(Campaign.admin_id == admin_id, Campaign.status == "Active").count()
        total_modules = db.query(TrainingModule).filter(TrainingModule.admin_id == admin_id).count()
    else:
        total_campaigns = db.query(Campaign).count()
        active_campaigns = db.query(Campaign).filter(Campaign.status == "Active").count()
        total_modules = db.query(TrainingModule).count()

    if total_employees > 0 and emp_ids:
        # Deriving from actual event logs
        from app.models.employee import EmployeeActivityEvent
        
        emails_sent = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id.in_(emp_ids),
            EmployeeActivityEvent.event_type == "email_sent"
        ).count()
        
        emails_opened = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id.in_(emp_ids),
            EmployeeActivityEvent.event_type == "email_opened"
        ).count()
        
        links_clicked = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id.in_(emp_ids),
            EmployeeActivityEvent.event_type == "link_clicked"
        ).count()
        
        emails_reported = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id.in_(emp_ids),
            EmployeeActivityEvent.event_type == "email_reported"
        ).count()
        
        # training completion rate
        total_assigned = db.query(TrainingAssignment).filter(
            TrainingAssignment.employee_id.in_(emp_ids)
        ).count()
        
        trainings_completed = db.query(TrainingCompletion).filter(
            TrainingCompletion.employee_id.in_(emp_ids),
            TrainingCompletion.status == "completed"
        ).count()
        
        # Risk and security calculations
        organization_risk_score = db.query(func.avg(Employee.risk_score)).filter(
            Employee.id.in_(emp_ids)
        ).scalar() or 0.0
        
    else:
        emails_sent = emails_opened = links_clicked = emails_reported = 0
        total_assigned = trainings_completed = 0
        organization_risk_score = 0.0

    report_rate = (emails_reported / emails_sent * 100.0) if emails_sent > 0 else 0.0
    click_rate = (links_clicked / emails_sent * 100.0) if emails_sent > 0 else 0.0
    training_completion_rate = (trainings_completed / total_assigned * 100.0) if total_assigned > 0 else 0.0
    average_security_score = max(0.0, 100.0 - float(organization_risk_score))

    return {
        "total_employees": total_employees,
        "total_companies": 1 if (admin_id or company_id) else db.query(Company).count(),
        "total_departments": total_departments,
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_modules": total_modules,
        "emails_sent": emails_sent,
        "emails_opened": emails_opened,
        "links_clicked": links_clicked,
        "emails_reported": emails_reported,
        "report_rate": round(report_rate, 2),
        "click_rate": round(click_rate, 2),
        "training_completion_rate": round(training_completion_rate, 2),
        "organization_risk_score": round(float(organization_risk_score), 2),
        "average_security_score": round(average_security_score, 1),
        "reports_submitted": emails_reported,  # backward compatibility
        "trainings_completed": trainings_completed  # backward compatibility
    }


def get_department_analytics(db: Session, admin_id=None, company_id=None) -> list:
    """Retrieve comparative metrics grouped by department, scoped to the tenant."""
    admin_id, company_id = _resolve_scope(db, admin_id, company_id)

    if company_id:
        departments = db.query(Department).filter(Department.company_id == company_id).all()
    elif admin_id:
        departments = db.query(Department).filter(Department.admin_id == admin_id).all()
    else:
        departments = db.query(Department).all()

    # Pre-fetch employees per department
    from app.models.employee import EmployeeActivityEvent
    
    results = []
    for dept in departments:
        emp_query = db.query(Employee).filter(
            Employee.department_id == dept.id,
            Employee.is_active == True
        )
        if company_id:
            emp_query = emp_query.filter(Employee.company_id == company_id)
        elif admin_id:
            emp_query = emp_query.filter(Employee.admin_id == admin_id)
            
        emp_list = emp_query.all()
        total_employees = len(emp_list)
        emp_ids = [e.id for e in emp_list]
        
        if total_employees > 0 and emp_ids:
            # 1. Counts of events
            emails_sent = db.query(EmployeeActivityEvent).filter(
                EmployeeActivityEvent.employee_id.in_(emp_ids),
                EmployeeActivityEvent.event_type == "email_sent"
            ).count()
            
            emails_opened = db.query(EmployeeActivityEvent).filter(
                EmployeeActivityEvent.employee_id.in_(emp_ids),
                EmployeeActivityEvent.event_type == "email_opened"
            ).count()
            
            links_clicked = db.query(EmployeeActivityEvent).filter(
                EmployeeActivityEvent.employee_id.in_(emp_ids),
                EmployeeActivityEvent.event_type == "link_clicked"
            ).count()
            
            emails_reported = db.query(EmployeeActivityEvent).filter(
                EmployeeActivityEvent.employee_id.in_(emp_ids),
                EmployeeActivityEvent.event_type == "email_reported"
            ).count()
            
            # 2. Training progress
            total_assigned = db.query(TrainingAssignment).filter(
                TrainingAssignment.employee_id.in_(emp_ids)
            ).count()
            
            completed_training = db.query(TrainingCompletion).filter(
                TrainingCompletion.employee_id.in_(emp_ids),
                TrainingCompletion.status == "completed"
            ).count()
            
            # 3. Employee scores and risk scores
            points_sum = db.query(func.sum(EmployeeActivityEvent.points_change)).filter(
                EmployeeActivityEvent.employee_id.in_(emp_ids)
            ).scalar() or 0
            average_employee_score = points_sum / total_employees
            
            risk_sum = sum(e.risk_score for e in emp_list)
            average_risk_score = risk_sum / total_employees
            
        else:
            emails_sent = emails_opened = links_clicked = emails_reported = 0
            total_assigned = completed_training = 0
            average_employee_score = 0.0
            average_risk_score = 0.0

        report_rate = (emails_reported / emails_sent * 100.0) if emails_sent > 0 else 0.0
        click_rate = (links_clicked / emails_sent * 100.0) if emails_sent > 0 else 0.0
        training_completion_rate = (completed_training / total_assigned * 100.0) if total_assigned > 0 else 0.0

        # Risk level determination
        if emails_sent > 0:
            if click_rate >= 15.0 and report_rate < 40.0:
                department_risk_level = "High"
            elif click_rate <= 10.0 and report_rate >= 60.0:
                department_risk_level = "Low"
            else:
                department_risk_level = "Medium"
        else:
            if average_risk_score > 70.0:
                department_risk_level = "High"
            elif average_risk_score <= 30.0:
                department_risk_level = "Low"
            else:
                department_risk_level = "Medium"

        results.append({
            "department_id": str(dept.id),
            "department_name": dept.name,
            "total_employees": total_employees,
            "headcount": total_employees,  # backward compatibility
            "emails_sent": emails_sent,
            "emails_opened": emails_opened,
            "links_clicked": links_clicked,
            "emails_reported": emails_reported,
            "report_rate": round(report_rate, 2),
            "click_rate": round(click_rate, 2),
            "training_completion_rate": round(training_completion_rate, 1),
            "average_employee_score": round(average_employee_score, 1),
            "average_risk_score": round(average_risk_score, 1),
            "security_score": round(100.0 - average_risk_score, 1), # backward compatibility
            "department_risk_level": department_risk_level
        })

    return results


def get_security_scores_trend(db: Session, admin_id=None, company_id=None) -> list:
    """Retrieve recent aggregated security scores over time, scoped to the tenant."""
    admin_id, company_id = _resolve_scope(db, admin_id, company_id)

    if company_id or admin_id:
        emp_sub = _employee_filter(db, admin_id, company_id).with_entities(Employee.id)
        scores = db.query(SecurityScore).filter(
            SecurityScore.employee_id.in_(emp_sub)
        ).order_by(SecurityScore.recorded_at.asc()).limit(50).all()
    else:
        scores = db.query(SecurityScore).order_by(SecurityScore.recorded_at.asc()).limit(50).all()

    return [
        {
            "id": str(s.id),
            "score": s.score,
            "recorded_at": s.recorded_at.isoformat()
        } for s in scores
    ]


def get_training_completion_stats(db: Session, admin_id=None, company_id=None) -> list:
    """Retrieve completion details grouped by training module, scoped to the tenant."""
    admin_id, company_id = _resolve_scope(db, admin_id, company_id)

    if admin_id:
        modules = db.query(TrainingModule).filter(TrainingModule.admin_id == admin_id).all()
    else:
        modules = db.query(TrainingModule).all()

    emp_sub = _employee_filter(db, admin_id, company_id).with_entities(Employee.id)
    has_filter = (company_id or admin_id)

    # 1. Fetch total assigned count per module
    total_assigned_query = db.query(
        TrainingAssignment.training_module_id,
        func.count(TrainingAssignment.id)
    )
    if has_filter:
        total_assigned_query = total_assigned_query.filter(TrainingAssignment.employee_id.in_(emp_sub))
    total_assigned_rows = total_assigned_query.group_by(TrainingAssignment.training_module_id).all()
    total_assigned_map = {row[0]: row[1] for row in total_assigned_rows if row[0] is not None}

    # 2. Fetch completed count per module
    completed_query = db.query(
        TrainingCompletion.training_module_id,
        func.count(TrainingCompletion.id)
    ).filter(
        TrainingCompletion.status == "completed"
    )
    if has_filter:
        completed_query = completed_query.filter(TrainingCompletion.employee_id.in_(emp_sub))
    completed_rows = completed_query.group_by(TrainingCompletion.training_module_id).all()
    completed_map = {row[0]: row[1] for row in completed_rows if row[0] is not None}

    results = []
    for mod in modules:
        total_assigned = total_assigned_map.get(mod.id, 0)
        completed = completed_map.get(mod.id, 0)

        results.append({
            "module_id": str(mod.id),
            "module_title": mod.title,
            "total_assigned": total_assigned,
            "completed": completed,
            "completion_rate": round((completed / total_assigned * 100.0), 1) if total_assigned > 0 else 0.0
        })
    return results


def get_ai_predictive_insights(db: Session, admin_id=None, company_id=None) -> dict:
    """Compute risk gaps and generate actionable mitigation tips, scoped to the tenant."""
    admin_id, company_id = _resolve_scope(db, admin_id, company_id)

    dept_stats = get_department_analytics(db, admin_id=admin_id, company_id=company_id)
    high_risk_depts = sorted(dept_stats, key=lambda x: x["avg_risk_score"], reverse=True)

    primary_threat_vector = "Spear Phishing"
    risk_summary = []
    mitigations = []

    if high_risk_depts:
        top_risk = high_risk_depts[0]
        if top_risk["avg_risk_score"] > 50.0:
            risk_summary.append(f"Critical Gap: Low Phishing Literacy in {top_risk['department_name']}")
            mitigations.append(f"Auto-schedule a targeted spear phishing simulation focusing on {top_risk['department_name']} roles.")

    emp_q = _employee_filter(db, admin_id, company_id)
    high_risk_count = emp_q.filter(Employee.risk_score >= 60.0).count()
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


def generate_insights_list(db: Session, admin_id=None, company_id=None) -> list:
    """Compile specific textual insights from database records."""
    from app.models.employee import Employee, EmployeeActivityEvent
    from app.models.department import Department
    from app.models.campaign import Campaign, CampaignRecipient, EmailTemplate
    from app.models.reported_email import ReportedEmail
    from app.models.training import TrainingAssignment, TrainingCompletion
    from sqlalchemy import func

    admin_id, company_id = _resolve_scope(db, admin_id, company_id)
    emp_q = _employee_filter(db, admin_id, company_id)
    emp_ids = [e.id for e in emp_q.all()]

    if not emp_ids:
        return ["No campaign activity recorded yet. Start a campaign to generate insights."]

    insights = []

    # 1. Employees who clicked but didn't report
    clicked_no_report = db.query(Employee).join(
        CampaignRecipient, CampaignRecipient.employee_id == Employee.id
    ).filter(
        Employee.id.in_(emp_ids),
        CampaignRecipient.clicked_at.isnot(None),
        CampaignRecipient.reported_at.is_(None)
    ).limit(3).all()
    if clicked_no_report:
        names = ", ".join(f"{e.first_name} {e.last_name}" for e in clicked_no_report)
        insights.append(f"⚠️ Employee Alert: {names} clicked on a simulated phishing link but failed to report it.")

    # 2. Departments with high click rates
    dept_stats = get_department_analytics(db, admin_id=admin_id, company_id=company_id)
    high_click_depts = [d for d in dept_stats if d["click_rate"] > 15.0]
    if high_click_depts:
        depts_str = ", ".join(f"{d['department_name']} ({d['click_rate']}% click rate)" for d in high_click_depts)
        insights.append(f"🔥 Vulnerability Alert: The {depts_str} department shows high link click behavior, requiring urgent simulation exercises.")

    # 3. Departments with low reporting rates
    low_report_depts = [d for d in dept_stats if d["report_rate"] < 30.0 and d["total_employees"] > 0]
    if low_report_depts:
        depts_str = ", ".join(f"{d['department_name']} ({d['report_rate']}% report rate)" for d in low_report_depts)
        insights.append(f"📈 Reporting Gap: The {depts_str} department has low reporting activity. Encourage employees to use the report phishing button.")

    # 4. Employees needing training
    enrolled_no_completion = db.query(Employee).join(
        TrainingAssignment, TrainingAssignment.employee_id == Employee.id
    ).outerjoin(
        TrainingCompletion, (TrainingCompletion.employee_id == Employee.id) & (TrainingCompletion.training_module_id == TrainingAssignment.training_module_id)
    ).filter(
        Employee.id.in_(emp_ids),
        TrainingAssignment.completed.is_(False),
        (TrainingCompletion.status.is_(None)) | (TrainingCompletion.status != "completed")
    ).limit(3).all()
    if enrolled_no_completion:
        names = ", ".join(f"{e.first_name} {e.last_name}" for e in enrolled_no_completion)
        insights.append(f"🎓 Training Required: {names} have incomplete assigned security training modules.")

    # 5. Top reporters
    top_reporters = db.query(
        Employee,
        func.count(EmployeeActivityEvent.id).label("reports_count")
    ).join(
        EmployeeActivityEvent, EmployeeActivityEvent.employee_id == Employee.id
    ).filter(
        Employee.id.in_(emp_ids),
        EmployeeActivityEvent.event_type == "email_reported"
    ).group_by(Employee.id).order_by(func.count(EmployeeActivityEvent.id).desc()).limit(3).all()
    if top_reporters:
        names = ", ".join(f"{row[0].first_name} {row[0].last_name} ({row[1]} reports)" for row in top_reporters)
        insights.append(f"🏆 Security Champions: {names} are performing exceptionally well in reporting phishing emails.")

    # 6. Riskiest campaign templates
    riskiest_templates = db.query(
        EmailTemplate.title,
        func.count(EmployeeActivityEvent.id).label("clicks_count")
    ).join(
        Campaign, Campaign.template_id == EmailTemplate.id
    ).join(
        EmployeeActivityEvent, EmployeeActivityEvent.campaign_id == Campaign.id
    ).filter(
        EmployeeActivityEvent.employee_id.in_(emp_ids),
        EmployeeActivityEvent.event_type == "link_clicked"
    ).group_by(EmailTemplate.title).order_by(func.count(EmployeeActivityEvent.id).desc()).limit(2).all()
    if riskiest_templates:
        templates_str = ", ".join(f"'{row[0]}' ({row[1]} clicks)" for row in riskiest_templates)
        insights.append(f"🚨 Riskiest Lures: The {templates_str} templates have the highest click rates.")

    # 7. Best performing departments
    best_depts = sorted(dept_stats, key=lambda x: x["security_score"], reverse=True)
    best_depts = [d for d in best_depts if d["total_employees"] > 0]
    if best_depts:
        best_dept = best_depts[0]
        insights.append(f"🌟 Leading Department: {best_dept['department_name']} is currently the best performing department with a security compliance rating of {best_dept['security_score']}%.")

    # 8. Campaigns with highest report rates
    highest_report_campaigns = db.query(
        Campaign.name,
        func.count(EmployeeActivityEvent.id).label("reports_count")
    ).join(
        EmployeeActivityEvent, EmployeeActivityEvent.campaign_id == Campaign.id
    ).filter(
        EmployeeActivityEvent.employee_id.in_(emp_ids),
        EmployeeActivityEvent.event_type == "email_reported"
    ).group_by(Campaign.name).order_by(func.count(EmployeeActivityEvent.id).desc()).limit(2).all()
    if highest_report_campaigns:
        campaigns_str = ", ".join(f"'{row[0]}' ({row[1]} reports)" for row in highest_report_campaigns)
        insights.append(f"📨 High Reporting: Campaign {campaigns_str} achieved the highest reporting numbers.")

    if not insights:
        insights.append("No critical risk patterns detected. Keep monitoring phishing simulations.")

    return insights


def get_insights_analytics(db: Session, admin_id=None, company_id=None) -> dict:
    """Retrieve database-backed insights analytics scoped to the tenant."""
    admin_id, company_id = _resolve_scope(db, admin_id, company_id)

    emp_q = _employee_filter(db, admin_id, company_id)
    total_emp = emp_q.count()

    emp_sub = emp_q.with_entities(Employee.id)

    # 1. Overall completion rate — scoped
    if total_emp > 0:
        total_assign = db.query(TrainingAssignment).filter(
            TrainingAssignment.employee_id.in_(emp_sub)
        ).count()
        completed_assign = db.query(TrainingCompletion).filter(
            TrainingCompletion.employee_id.in_(emp_sub),
            TrainingCompletion.status == "completed"
        ).count()
    else:
        total_assign = completed_assign = 0
    overall_completion = f"{round((completed_assign / total_assign * 100.0), 1)}%" if total_assign > 0 else "0.0%"

    # 2. Average Quiz rating — scoped
    if total_emp > 0:
        avg_quiz = db.query(func.avg(QuizAttempt.score)).filter(
            QuizAttempt.employee_id.in_(emp_sub)
        ).scalar() or 0.0
    else:
        avg_quiz = 0.0
    avg_quiz_rating = f"{round(float(avg_quiz), 1)}/100"

    # 3. Phish click rate — scoped to this admin's campaigns / employees
    if total_emp > 0:
        total_recipients = db.query(CampaignRecipient).filter(
            CampaignRecipient.employee_id.in_(emp_sub)
        ).count()
        clicked_recipients = db.query(CampaignRecipient).filter(
            CampaignRecipient.employee_id.in_(emp_sub),
            CampaignRecipient.status == "Clicked"
        ).count()
    else:
        total_recipients = clicked_recipients = 0
    phish_click_rate = f"{round((clicked_recipients / total_recipients * 100.0), 1)}%" if total_recipients > 0 else "0.0%"

    # 4. Empowered Employees — scoped
    if total_emp > 0:
        completed_emp = db.query(Employee).filter(
            Employee.id.in_(
                db.query(TrainingAssignment.employee_id).filter(
                    TrainingAssignment.completed == True,
                    TrainingAssignment.employee_id.in_(emp_sub)
                ).subquery()
            )
        ).count()
    else:
        completed_emp = 0
    empowered_employees = f"{completed_emp} / {total_emp}"

    # Pre-fetch stats maps grouped by department to avoid N+1 queries
    stats_query = db.query(
        Employee.department_id,
        func.count(Employee.id).label("headcount"),
        func.avg(Employee.risk_score).label("avg_risk")
    )
    if company_id:
        stats_query = stats_query.filter(Employee.company_id == company_id)
    elif admin_id:
        stats_query = stats_query.filter(Employee.admin_id == admin_id)
    stats_rows = stats_query.group_by(Employee.department_id).all()
    stats_map = {row[0]: (row[1] or 0, float(row[2]) if row[2] is not None else 0.0) for row in stats_rows if row[0] is not None}
    
    total_assign_query = db.query(
        Employee.department_id,
        func.count(TrainingAssignment.id).label("total_assignments")
    ).join(
        TrainingAssignment, TrainingAssignment.employee_id == Employee.id
    )
    if company_id:
        total_assign_query = total_assign_query.filter(Employee.company_id == company_id)
    elif admin_id:
        total_assign_query = total_assign_query.filter(Employee.admin_id == admin_id)
    total_assign_rows = total_assign_query.group_by(Employee.department_id).all()
    total_assign_map = {row[0]: (row[1] or 0) for row in total_assign_rows if row[0] is not None}

    completed_assign_query = db.query(
        Employee.department_id,
        func.count(TrainingCompletion.id).label("completed_assignments")
    ).join(
        TrainingCompletion, TrainingCompletion.employee_id == Employee.id
    ).join(
        TrainingAssignment,
        (TrainingCompletion.employee_id == TrainingAssignment.employee_id) &
        (TrainingCompletion.training_module_id == TrainingAssignment.training_module_id)
    ).filter(
        TrainingCompletion.status == "completed"
    )
    if company_id:
        completed_assign_query = completed_assign_query.filter(Employee.company_id == company_id)
    elif admin_id:
        completed_assign_query = completed_assign_query.filter(Employee.admin_id == admin_id)
    completed_assign_rows = completed_assign_query.group_by(Employee.department_id).all()
    completed_assign_map = {row[0]: (row[1] or 0) for row in completed_assign_rows if row[0] is not None}

    avg_quiz_query = db.query(
        Employee.department_id,
        func.avg(QuizAttempt.score).label("avg_score")
    ).join(
        QuizAttempt, QuizAttempt.employee_id == Employee.id
    )
    if company_id:
        avg_quiz_query = avg_quiz_query.filter(Employee.company_id == company_id)
    elif admin_id:
        avg_quiz_query = avg_quiz_query.filter(Employee.admin_id == admin_id)
    avg_quiz_rows = avg_quiz_query.group_by(Employee.department_id).all()
    avg_quiz_map = {row[0]: float(row[1]) if row[1] is not None else 0.0 for row in avg_quiz_rows if row[0] is not None}

    clicks_query = db.query(
        Employee.department_id,
        func.count(CampaignRecipient.id).label("clicks_count")
    ).join(
        CampaignRecipient, CampaignRecipient.employee_id == Employee.id
    ).filter(
        CampaignRecipient.status == "Clicked"
    )
    if company_id:
        clicks_query = clicks_query.filter(Employee.company_id == company_id)
    elif admin_id:
        clicks_query = clicks_query.filter(Employee.admin_id == admin_id)
    clicks_rows = clicks_query.group_by(Employee.department_id).all()
    clicks_map = {row[0]: (row[1] or 0) for row in clicks_rows if row[0] is not None}

    # 5. Department Performance — scoped
    if company_id:
        departments = db.query(Department).filter(Department.company_id == company_id).all()
        if not departments:
            departments = db.query(Department).all()
    else:
        departments = db.query(Department).all()

    dept_performance = []
    for d in departments:
        headcount, _ = stats_map.get(d.id, (0, 0.0))
        if headcount == 0:
            dept_performance.append({"name": d.name, "completion": 0.0, "score": 0.0})
            continue

        tot_a = total_assign_map.get(d.id, 0)
        com_a = completed_assign_map.get(d.id, 0)
        comp_rate = round((com_a / tot_a * 100.0), 1) if tot_a > 0 else 0.0
        avg_q = avg_quiz_map.get(d.id, 0.0)

        dept_performance.append({
            "name": d.name,
            "completion": comp_rate,
            "score": round(avg_q, 1)
        })

    if not dept_performance:
        dept_performance = [
            {"name": "Engineering", "completion": 0.0, "score": 0.0},
            {"name": "Security Operations", "completion": 0.0, "score": 0.0}
        ]

    # 6. Lure distribution — scoped to admin's campaigns
    from app.models.campaign import EmailTemplate
    lure_q = db.query(
        EmailTemplate.category,
        func.count(CampaignRecipient.id)
    ).join(
        Campaign, Campaign.id == CampaignRecipient.campaign_id
    ).join(
        EmailTemplate, EmailTemplate.id == Campaign.template_id
    ).filter(
        CampaignRecipient.status == "Clicked"
    )
    if admin_id:
        lure_q = lure_q.filter(Campaign.admin_id == admin_id)
    lure_results = lure_q.group_by(EmailTemplate.category).all()

    lure_distribution = []
    colors = ["var(--color-primary)", "var(--color-success)", "var(--color-warning)", "var(--color-danger)", "var(--color-teal)"]
    for i, res in enumerate(lure_results):
        lure_distribution.append({
            "name": res[0] or "Phishing",
            "value": res[1],
            "color": colors[i % len(colors)]
        })
    if not lure_distribution:
        lure_distribution = [
            {"name": "Credential Harvesting", "value": 0, "color": colors[0]},
            {"name": "Urgent Attachments", "value": 0, "color": colors[1]},
            {"name": "Authority Impersonation", "value": 0, "color": colors[2]}
        ]

    # 7. Trends — calculated dynamically from EmployeeActivityEvents
    from datetime import datetime, timedelta
    trends = []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    now = datetime.utcnow()
    
    for i in range(4, -1, -1):
        month_date = now - timedelta(days=30 * i)
        month_name = months[month_date.month - 1]
        
        clicks_count = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id.in_(emp_sub),
            EmployeeActivityEvent.event_type == "link_clicked",
            func.extract('month', EmployeeActivityEvent.created_at) == month_date.month,
            func.extract('year', EmployeeActivityEvent.created_at) == month_date.year
        ).count()
        
        reports_count = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id.in_(emp_sub),
            EmployeeActivityEvent.event_type == "email_reported",
            func.extract('month', EmployeeActivityEvent.created_at) == month_date.month,
            func.extract('year', EmployeeActivityEvent.created_at) == month_date.year
        ).count()
        
        trends.append({
            "month": month_name,
            "clicks": clicks_count,
            "reports": reports_count
        })

    # Calculate Campaign Success Rates (Avoidance %)
    campaign_avoidance = []
    c_query = db.query(Campaign).filter(
        Campaign.admin_id == admin_id if admin_id else True
    ).order_by(Campaign.created_at.desc()).limit(5).all()
    
    for c in c_query:
        total_rec = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id).count()
        clicked_rec = db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == c.id,
            CampaignRecipient.status == "Clicked"
        ).count()
        
        success_rate = (1.0 - (clicked_rec / total_rec)) * 100.0 if total_rec > 0 else 100.0
        campaign_avoidance.append({
            "name": c.name,
            "rate": round(success_rate, 1)
        })
        
    if not campaign_avoidance:
        campaign_avoidance = [
            {"name": "No Campaigns", "rate": 100.0}
        ]

    # Calculate monthly training progress trends
    training_trends = []
    for i in range(4, -1, -1):
        month_date = now - timedelta(days=30 * i)
        month_name = months[month_date.month - 1]
        
        completed_courses = db.query(TrainingCompletion).filter(
            TrainingCompletion.employee_id.in_(emp_sub),
            TrainingCompletion.status == "completed",
            func.extract('month', TrainingCompletion.completed_at) == month_date.month,
            func.extract('year', TrainingCompletion.completed_at) == month_date.year
        ).count()
        
        enrolled_courses = db.query(TrainingAssignment).filter(
            TrainingAssignment.employee_id.in_(emp_sub),
            func.extract('month', TrainingAssignment.created_at) == month_date.month,
            func.extract('year', TrainingAssignment.created_at) == month_date.year
        ).count()
        
        training_trends.append({
            "month": month_name,
            "completed": completed_courses,
            "enrolled": enrolled_courses
        })

    # 8. High Risk Departments — scoped
    high_risk_dept = []
    for d in departments:
        headcount, avg_risk = stats_map.get(d.id, (0, 0.0))
        if headcount == 0:
            continue

        clicks_count = clicks_map.get(d.id, 0)
        
        risk_level = "High" if avg_risk > 60.0 else "Medium" if avg_risk > 30.0 else "Low"
        advice = "Assign urgent micro-learning templates focusing on authority fraud."
        if risk_level == "Medium":
            advice = "Schedule landing-page identification quizzes."
        elif risk_level == "Low":
            advice = "Routine refresh training for general ledger workflows."
            
        high_risk_dept.append({
            "name": d.name,
            "risk": risk_level,
            "clicks": clicks_count,
            "advice": advice
        })
    high_risk_dept = sorted(high_risk_dept, key=lambda x: x["clicks"], reverse=True)[:3]
    if not high_risk_dept:
        high_risk_dept = [
            {"name": "Marketing & Sales", "risk": "Low", "clicks": 0, "advice": "Routine refresh training for general ledger workflows."}
        ]

    return {
        "overallCompletion": overall_completion,
        "avgQuizRating": avg_quiz_rating,
        "phishClickRate": phish_click_rate,
        "empoweredEmployees": empowered_employees,
        "deptPerformance": dept_performance,
        "lureDistribution": lure_distribution,
        "trends": trends,
        "highRiskDept": high_risk_dept,
        "text_insights": generate_insights_list(db, admin_id=admin_id, company_id=company_id),
        "campaignSuccessRates": campaign_avoidance,
        "trainingTrends": training_trends
    }


def get_employee_behavior_analytics(db: Session, admin_id=None, company_id=None) -> list:
    """Retrieve individual employee risk ratings and behavior metrics scoped to the tenant."""
    admin_id, company_id = _resolve_scope(db, admin_id, company_id)
    emp_q = _employee_filter(db, admin_id, company_id)
    employees = emp_q.all()

    # Pre-fetch department mapping
    depts = {d.id: d.name for d in db.query(Department).all()}

    # Bulk fetch events for efficiency
    from app.models.employee import EmployeeActivityEvent
    
    # Sum points_change per employee
    points_rows = db.query(
        EmployeeActivityEvent.employee_id,
        func.sum(EmployeeActivityEvent.points_change)
    ).group_by(EmployeeActivityEvent.employee_id).all()
    points_map = {row[0]: int(row[1]) for row in points_rows if row[0] is not None}

    # Count reported events per employee
    reported_rows = db.query(
        EmployeeActivityEvent.employee_id,
        func.count(EmployeeActivityEvent.id)
    ).filter(EmployeeActivityEvent.event_type == "email_reported").group_by(EmployeeActivityEvent.employee_id).all()
    reported_map = {row[0]: int(row[1]) for row in reported_rows if row[0] is not None}

    # Count click events per employee
    clicked_rows = db.query(
        EmployeeActivityEvent.employee_id,
        func.count(EmployeeActivityEvent.id)
    ).filter(EmployeeActivityEvent.event_type == "link_clicked").group_by(EmployeeActivityEvent.employee_id).all()
    clicked_map = {row[0]: int(row[1]) for row in clicked_rows if row[0] is not None}

    # Training modules completion count
    training_total_rows = db.query(
        TrainingAssignment.employee_id,
        func.count(TrainingAssignment.id)
    ).group_by(TrainingAssignment.employee_id).all()
    training_total_map = {row[0]: int(row[1]) for row in training_total_rows if row[0] is not None}

    training_completed_rows = db.query(
        TrainingCompletion.employee_id,
        func.count(TrainingCompletion.id)
    ).filter(TrainingCompletion.status == "completed").group_by(TrainingCompletion.employee_id).all()
    training_completed_map = {row[0]: int(row[1]) for row in training_completed_rows if row[0] is not None}

    results = []
    for emp in employees:
        total_points = points_map.get(emp.id, 0)
        report_count = reported_map.get(emp.id, 0)
        click_count = clicked_map.get(emp.id, 0)
        
        tot_t = training_total_map.get(emp.id, 0)
        com_t = training_completed_map.get(emp.id, 0)
        training_progress = f"{round(com_t / tot_t * 100.0, 1)}%" if tot_t > 0 else "0.0%"
        
        results.append({
            "employee_id": str(emp.id),
            "name": emp.name or f"{emp.first_name} {emp.last_name}".strip() or "Employee",
            "email": emp.email,
            "department": depts.get(emp.department_id, "General"),
            "department_name": depts.get(emp.department_id, "General"),
            "risk_score": emp.risk_score,
            "status": emp.status,
            "total_points": total_points,
            "report_count": report_count,
            "click_count": click_count,
            "training_progress": training_progress
        })
        
    return results

