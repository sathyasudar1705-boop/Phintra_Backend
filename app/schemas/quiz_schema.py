from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

# Quiz Question Schemas
class QuizQuestionBase(BaseModel):
    question_text: str
    options: List[str]
    correct_option_index: int

class QuizQuestionCreate(QuizQuestionBase):
    pass

class QuizQuestionResponse(QuizQuestionBase):
    id: UUID
    quiz_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Quiz Schemas
class QuizBase(BaseModel):
    module_id: UUID
    passing_score: int = 100

class QuizCreate(QuizBase):
    pass

class QuizResponse(QuizBase):
    id: UUID
    admin_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    questions: List[QuizQuestionResponse] = []

    class Config:
        from_attributes = True


# Quiz Attempt Schemas
class QuizAttemptBase(BaseModel):
    employee_id: UUID
    quiz_id: UUID
    score: int
    passed: bool

class QuizAttemptCreate(QuizAttemptBase):
    pass

class QuizAttemptResponse(QuizAttemptBase):
    id: UUID
    attempted_at: datetime

    class Config:
        from_attributes = True

class QuizAttemptSubmit(BaseModel):
    employee_id: UUID
    answers: List[int] # index of options selected for each question
