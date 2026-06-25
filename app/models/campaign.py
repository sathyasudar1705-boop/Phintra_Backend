import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False) # Link Phishing, Spear Phishing, Credential Harvesting, MFA Bypass
    status = Column(String, default="Draft", nullable=False) # Draft, Active, Completed
    launch_date = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True)
    sender_profile_id = Column(UUID(as_uuid=True), ForeignKey("sender_profiles.profile_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    recipients = relationship("CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan")
    sender_profile = relationship("SenderProfile")


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    email_log_id = Column(UUID(as_uuid=True), ForeignKey("email_logs.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    reported_at = Column(DateTime(timezone=True), nullable=True)
    training_completed_at = Column(DateTime(timezone=True), nullable=True)
    quiz_completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="Sent", nullable=False) # Sent, Opened, Clicked, Reported
    track_id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="recipients")
    employee = relationship("Employee", back_populates="campaign_recipients")


class CampaignClick(Base):
    __tablename__ = "campaign_clicks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)
    track_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    clicked_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, default="Clicked", nullable=False)


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body_html = Column(String, nullable=False)
    body_text = Column(String, nullable=True)
    category = Column(String, nullable=True, default="Phishing")
    difficulty = Column(String, nullable=True, default="Medium")
    sender_name = Column(String, nullable=True, default="System Notification")
    sender_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @property
    def template_id(self):
        return self.id

    @property
    def template_name(self):
        return self.title

    @property
    def sender_display_name(self):
        return self.sender_name

    @property
    def created_by_admin_id(self):
        return self.admin_id

    @property
    def is_system_template(self):
        return self.admin_id is None



class AwarenessPage(Base):
    __tablename__ = "awareness_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    html_content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ReportLog(Base):
    __tablename__ = "report_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False) # report or safe
    reported_at = Column(DateTime(timezone=True), server_default=func.now())

    # relationships
    employee = relationship("Employee", backref="report_logs")
    campaign = relationship("Campaign", backref="report_logs")
