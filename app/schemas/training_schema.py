from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Training Module Schemas
class TrainingModuleBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    duration: int = 10  # in minutes
    difficulty: Optional[str] = None
    video_url: Optional[str] = None
    uploaded_video_url: Optional[str] = None
    xp_reward: Optional[int] = 50

class TrainingModuleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    duration: int = 10
    difficulty: Optional[str] = None
    video_url: Optional[str] = None
    xp_reward: Optional[int] = 50

class TrainingModuleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    duration: Optional[int] = None
    difficulty: Optional[str] = None
    video_url: Optional[str] = None
    xp_reward: Optional[int] = None

class TrainingModuleResponse(TrainingModuleBase):
    id: UUID
    admin_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Training Assignment Schemas
class TrainingAssignmentBase(BaseModel):
    employee_id: Optional[UUID] = None
    training_module_id: Optional[UUID] = None
    admin_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    assign_all: Optional[bool] = False

class TrainingAssignmentCreate(TrainingAssignmentBase):
    pass

class TrainingAssignmentUpdate(BaseModel):
    employee_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    company_id: Optional[UUID] = None

class TrainingAssignmentResponse(BaseModel):
    id: UUID
    training_module_id: UUID
    admin_id: UUID
    employee_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Kept for compatibility with other modules
class TrainingAssignBulkRequest(BaseModel):
    employee_ids: List[UUID]


# Training Completion Schemas
class TrainingCompletionResponse(BaseModel):
    id: UUID
    training_module_id: UUID
    employee_id: UUID
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
