import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), nullable=False)
    sender_role = Column(String, nullable=False) # "employee" or "admin"
    sender_name = Column(String, nullable=False)
    message_text = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reported_email_id = Column(UUID(as_uuid=True), ForeignKey("reported_emails.id", ondelete="CASCADE"), nullable=True)

    employee = relationship("Employee", backref="employee_messages")
    admin = relationship("User", backref="admin_messages")
    reported_email = relationship("ReportedEmail", backref="messages")
