import uuid
import enum
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class TrainingModule(Base):
    __tablename__ = "training_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    duration = Column(Integer, nullable=True, default=10)  # Python attr; DB uses duration_minutes (handled via raw SQL)
    difficulty = Column(String, nullable=True)
    video_url = Column(String, nullable=True)  # external link
    uploaded_video_url = Column(String, nullable=True)  # stored file path
    xp_reward = Column(Integer, nullable=False, default=50)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Keep compatibility with existing relationships if any
    assignments = relationship("TrainingAssignment", back_populates="module", cascade="all, delete-orphan")
    completions = relationship("TrainingCompletion", back_populates="training_module", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="module", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="module", cascade="all, delete-orphan")


class TrainingAssignment(Base):
    __tablename__ = "training_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    training_module_id = Column("module_id", UUID(as_uuid=True), ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    progress = Column(Integer, nullable=False, default=0)
    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    module = relationship("TrainingModule", back_populates="assignments")
    employee = relationship("Employee", back_populates="training_assignments")
    department = relationship("Department")
    company = relationship("Company")


class CompletionStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TrainingCompletion(Base):
    __tablename__ = "training_completions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    training_module_id = Column(UUID(as_uuid=True), ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(CompletionStatus), nullable=False, default=CompletionStatus.NOT_STARTED)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    training_module = relationship("TrainingModule", back_populates="completions")
    employee = relationship("Employee")
