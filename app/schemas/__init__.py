from app.schemas.company_schema import CompanyBase, CompanyCreate, CompanyUpdate, CompanyResponse
from app.schemas.user_schema import UserBase, UserCreate, UserUpdate, UserResponse, Token, TokenData
from app.schemas.department_schema import DepartmentBase, DepartmentCreate, DepartmentUpdate, DepartmentResponse, DepartmentDetailResponse
from app.schemas.employee_schema import EmployeeBase, EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeDetailResponse
from app.schemas.campaign_schema import (
    EmailTemplateBase, EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse,
    AwarenessPageBase, AwarenessPageCreate, AwarenessPageUpdate, AwarenessPageResponse,
    CampaignBase, CampaignCreate, CampaignUpdate, CampaignResponse,
    CampaignRecipientBase, CampaignRecipientCreate, CampaignRecipientResponse, CampaignAssignRequest
)
from app.schemas.training_schema import (
    TrainingModuleBase, TrainingModuleCreate, TrainingModuleUpdate, TrainingModuleResponse,
    TrainingAssignmentBase, TrainingAssignmentCreate, TrainingAssignmentUpdate, TrainingAssignmentResponse,
    TrainingAssignBulkRequest
)
from app.schemas.quiz_schema import (
    QuizQuestionBase, QuizQuestionCreate, QuizQuestionResponse,
    QuizBase, QuizCreate, QuizResponse,
    QuizAttemptBase, QuizAttemptCreate, QuizAttemptResponse, QuizAttemptSubmit
)
from app.schemas.certificate_schema import (
    CertificateBase, CertificateCreate, CertificateResponse,
    RewardBase, RewardCreate, RewardResponse,
    ReportedEmailBase, ReportedEmailCreate, ReportedEmailUpdate, ReportedEmailResponse
)
from app.schemas.email_schema import ThreatFeedBase, ThreatFeedCreate, ThreatFeedResponse, EmailLogResponse, EmailSendRequest
from app.schemas.notification_schema import NotificationBase, NotificationCreate, NotificationResponse, AuditLogResponse, SecurityScoreResponse

__all__ = [
    "CompanyBase", "CompanyCreate", "CompanyUpdate", "CompanyResponse",
    "UserBase", "UserCreate", "UserUpdate", "UserResponse", "Token", "TokenData",
    "DepartmentBase", "DepartmentCreate", "DepartmentUpdate", "DepartmentResponse", "DepartmentDetailResponse",
    "EmployeeBase", "EmployeeCreate", "EmployeeUpdate", "EmployeeResponse", "EmployeeDetailResponse",
    "EmailTemplateBase", "EmailTemplateCreate", "EmailTemplateUpdate", "EmailTemplateResponse",
    "AwarenessPageBase", "AwarenessPageCreate", "AwarenessPageUpdate", "AwarenessPageResponse",
    "CampaignBase", "CampaignCreate", "CampaignUpdate", "CampaignResponse",
    "CampaignRecipientBase", "CampaignRecipientCreate", "CampaignRecipientResponse", "CampaignAssignRequest",
    "TrainingModuleBase", "TrainingModuleCreate", "TrainingModuleUpdate", "TrainingModuleResponse",
    "TrainingAssignmentBase", "TrainingAssignmentCreate", "TrainingAssignmentUpdate", "TrainingAssignmentResponse",
    "TrainingAssignBulkRequest",
    "QuizQuestionBase", "QuizQuestionCreate", "QuizQuestionResponse",
    "QuizBase", "QuizCreate", "QuizResponse",
    "QuizAttemptBase", "QuizAttemptCreate", "QuizAttemptResponse", "QuizAttemptSubmit",
    "CertificateBase", "CertificateCreate", "CertificateResponse",
    "RewardBase", "RewardCreate", "RewardResponse",
    "ReportedEmailBase", "ReportedEmailCreate", "ReportedEmailUpdate", "ReportedEmailResponse",
    "ThreatFeedBase", "ThreatFeedCreate", "ThreatFeedResponse", "EmailLogResponse", "EmailSendRequest",
    "NotificationBase", "NotificationCreate", "NotificationResponse", "AuditLogResponse", "SecurityScoreResponse"
]
