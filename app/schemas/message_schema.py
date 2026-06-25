from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class MessageCreate(BaseModel):
    message_text: str

class AdminMessageCreate(BaseModel):
    employee_id: UUID
    message_text: str

class MessageRead(BaseModel):
    id: UUID
    employee_id: UUID
    admin_id: UUID
    sender_id: UUID
    sender_role: str
    sender_name: str
    message_text: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ThreadInfo(BaseModel):
    employee_id: UUID
    employee_name: str
    employee_email: str
    department_name: str
    last_message: str
    last_message_at: datetime
    unread_count: int
