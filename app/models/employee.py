import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func, Boolean, Integer
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
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    dashboard_token = Column(String, nullable=True)
    dashboard_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    from sqlalchemy import UniqueConstraint
    __table_args__ = (UniqueConstraint('admin_id', 'email', name='uix_admin_email'),)

    company = relationship("Company", back_populates="employees")
    department = relationship("Department", back_populates="employees", foreign_keys=[department_id])
    campaign_recipients = relationship("CampaignRecipient", back_populates="employee", cascade="all, delete-orphan")
    training_assignments = relationship("TrainingAssignment", back_populates="employee", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="employee", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="employee", cascade="all, delete-orphan")
    rewards = relationship("Reward", back_populates="employee", cascade="all, delete-orphan")
    reported_emails = relationship("ReportedEmail", back_populates="employee", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="employee", cascade="all, delete-orphan")
    security_scores = relationship("SecurityScore", back_populates="employee", cascade="all, delete-orphan")
    activity_events = relationship("EmployeeActivityEvent", back_populates="employee", cascade="all, delete-orphan")


class EmployeeActivityEvent(Base):
    __tablename__ = "employee_activity_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(String, nullable=False) # email_sent, email_opened, link_clicked, email_reported, training_completed, quiz_passed, quiz_failed
    event_value = Column(String, nullable=True)
    points_change = Column(Integer, default=0, nullable=False)
    risk_change = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee", back_populates="activity_events")

