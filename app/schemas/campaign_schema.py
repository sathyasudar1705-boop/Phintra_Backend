from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Email Template Schemas
class EmailTemplateBase(BaseModel):
    title: Optional[str] = None
    template_name: Optional[str] = None
    subject: str
    body_html: str
    body_text: Optional[str] = None
    category: Optional[str] = "Phishing"
    difficulty: Optional[str] = "Medium"
    sender_name: Optional[str] = None
    sender_display_name: Optional[str] = None
    sender_email: Optional[str] = None

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    title: Optional[str] = None
    template_name: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    sender_name: Optional[str] = None
    sender_display_name: Optional[str] = None
    sender_email: Optional[str] = None

class EmailTemplateResponse(BaseModel):
    id: UUID
    template_id: UUID
    title: str
    template_name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    category: Optional[str] = "Phishing"
    difficulty: Optional[str] = "Medium"
    sender_name: Optional[str] = "System Notification"
    sender_display_name: Optional[str] = "System Notification"
    sender_email: Optional[str] = None
    admin_id: Optional[UUID] = None
    created_by_admin_id: Optional[UUID] = None
    is_system_template: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Awareness Page Schemas
class AwarenessPageBase(BaseModel):
    title: str
    html_content: str

class AwarenessPageCreate(AwarenessPageBase):
    pass

class AwarenessPageUpdate(BaseModel):
    title: Optional[str] = None
    html_content: Optional[str] = None

class AwarenessPageResponse(AwarenessPageBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Campaign Schemas
class CampaignBase(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    type: Optional[str] = "Link Phishing"
    campaign_type: Optional[str] = None
    status: str = "Draft" # Draft, Active, Completed
    launch_date: Optional[datetime] = None
    department_id: Optional[UUID] = None

class CampaignCreate(CampaignBase):
    created_by: Optional[UUID] = None
    template_id: Optional[UUID] = None
    employee_ids: Optional[List[UUID]] = None

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    type: Optional[str] = None
    campaign_type: Optional[str] = None
    status: Optional[str] = None
    launch_date: Optional[datetime] = None
    department_id: Optional[UUID] = None
    template_id: Optional[UUID] = None

class CampaignResponse(CampaignBase):
    id: UUID
    created_by: Optional[UUID] = None
    template_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    sent: int = 0
    opened: int = 0
    clicked: int = 0
    reported: int = 0
    department: str = "All Departments"
    date: str = ""
    employee_count: int = 0
    success_rate: float = 100.0

    class Config:
        from_attributes = True


# Campaign Recipient Schemas
class CampaignRecipientBase(BaseModel):
    campaign_id: UUID
    employee_id: UUID
    status: str = "Sent" # Sent, Opened, Clicked, Reported

class CampaignRecipientCreate(CampaignRecipientBase):
    pass

class CampaignRecipientResponse(CampaignRecipientBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CampaignAssignRequest(BaseModel):
    employee_ids: List[UUID]


# Click and Alert Schemas
class CampaignClickCreate(BaseModel):
    ip_address: Optional[str] = "127.0.0.1"
    user_agent: Optional[str] = "Unknown"


class CampaignClickResponse(BaseModel):
    id: UUID
    admin_id: UUID
    campaign_id: UUID
    employee_id: UUID
    email: str
    track_id: UUID
    clicked_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class CampaignAlertResponse(BaseModel):
    employee_name: str
    employee_email: str
    campaign_name: str
    clicked_at: datetime
    risk_status: str


class ClickedEmployeeInfo(BaseModel):
    name: str
    email: str
    department: str
    clicked_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class NonClickedEmployeeInfo(BaseModel):
    name: str
    email: str
    department: str
    status: str


class DepartmentRiskInfo(BaseModel):
    department_name: str
    click_count: int
    total_employees: int


class ReportedEmployeeInfo(BaseModel):
    name: str
    email: str
    department: str
    reported_at: datetime


class CampaignAnalyticsResponse(BaseModel):
    total_sent: int
    total_delivered: int
    total_failed: int
    total_clicked: int
    total_reported: int
    click_rate_percentage: float
    reported_rate_percentage: float
    clicked_employees: List[ClickedEmployeeInfo]
    reported_employees: List[ReportedEmployeeInfo]
    non_clicked_employees: List[NonClickedEmployeeInfo]
    department_risk: List[DepartmentRiskInfo]
    total_opened: Optional[int] = 0
    open_rate_percentage: Optional[float] = 0.0
    training_completed_count: Optional[int] = 0
    training_completion_rate_percentage: Optional[float] = 0.0
