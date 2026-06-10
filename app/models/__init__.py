from app.database import Base
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.company import Company
from app.models.campaign import Campaign, CampaignRecipient, EmailTemplate, AwarenessPage, ReportLog
from app.models.training import TrainingModule, TrainingAssignment
from app.models.quiz import Quiz, QuizQuestion, QuizAttempt
from app.models.certificate import Certificate, Reward, ReportedEmail
from app.models.email_log import EmailLog, ThreatFeed
from app.models.audit_log import AuditLog, SecurityScore
from app.models.notification import Notification

# Create direct list of model classes for helper access
__all__ = [
    "Base",
    "User",
    "Company",
    "Department",
    "Employee",
    "Campaign",
    "CampaignRecipient",
    "EmailTemplate",
    "AwarenessPage",
    "ReportLog",
    "TrainingModule",
    "TrainingAssignment",
    "Quiz",
    "QuizQuestion",
    "QuizAttempt",
    "Certificate",
    "Reward",
    "ReportedEmail",
    "EmailLog",
    "ThreatFeed",
    "AuditLog",
    "SecurityScore",
    "Notification"
]
