import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=False, index=True, unique=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    risk_score = Column(Float, default=0.0, nullable=False)
    status = Column(String, default="Low Risk", nullable=False) # Low Risk, Medium Risk, High Risk, Critical
    role = Column(String, default="employee", server_default="employee", nullable=False)
    hashed_password = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)  # bcrypt hash for employee login
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    from sqlalchemy import UniqueConstraint
    __table_args__ = (UniqueConstraint('admin_id', 'email', name='uix_admin_email'),)

    department = relationship("Department", back_populates="employees", foreign_keys=[department_id])
    campaign_recipients = relationship("CampaignRecipient", back_populates="employee", cascade="all, delete-orphan")
    training_assignments = relationship("TrainingAssignment", back_populates="employee", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="employee", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="employee", cascade="all, delete-orphan")
    rewards = relationship("Reward", back_populates="employee", cascade="all, delete-orphan")
    reported_emails = relationship("ReportedEmail", back_populates="employee", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="employee", cascade="all, delete-orphan")
    security_scores = relationship("SecurityScore", back_populates="employee", cascade="all, delete-orphan")
