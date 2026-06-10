from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Threat Feed Schemas
class ThreatFeedBase(BaseModel):
    title: str
    description: Optional[str] = None
    source: Optional[str] = None
    severity: str = "Low" # Low, Medium, High, Critical

class ThreatFeedCreate(ThreatFeedBase):
    pass

class ThreatFeedResponse(ThreatFeedBase):
    id: UUID
    published_at: datetime

    class Config:
        from_attributes = True


# Email Log Schemas
class EmailLogResponse(BaseModel):
    id: UUID
    campaign_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    recipient_email: str
    subject: str
    status: str
    error_message: Optional[str] = None
    employee_id: Optional[UUID] = None
    sent_at: datetime

    class Config:
        from_attributes = True


# Outgoing Send Request Schema
class EmailSendRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str

# Outgoing Bulk Send Request Schema
class EmailSendBulkRequest(BaseModel):
    emails: List[EmailStr]
    subject: str
    body: str

# Email Test Request Schema
class EmailTestRequest(BaseModel):
    to_email: EmailStr

# Email Campaign Send Request Schema
class EmailCampaignSendRequest(BaseModel):
    campaign_id: UUID
    template_id: UUID
    emails: List[EmailStr]
    subject: str
    body: str

