import smtplib
from email.message import EmailMessage
from typing import Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.email_log import EmailLog
from app.database import SessionLocal

def send_email(*args, **kwargs) -> bool:
    """
    Sends email via SMTP using configuration from settings.
    Supports two signatures:
    1. send_email(db: Session, to_email: str, subject: str, body: str) -> bool
    2. send_email(to_email: str, subject: str, body: str) -> bool
    
    RESTRICTION: Safe awareness and training communications only.
    No tracking, no actual phishing payloads, no credential collection.
    Logs transaction outcome to the database.
    """
    # Extract arguments dynamically to handle both old and new signatures
    db = None
    to_email = None
    subject = None
    body = None

    if len(args) > 0 and (isinstance(args[0], Session) or hasattr(args[0], "commit")):
        # Signature 1: send_email(db, to_email, subject, body)
        db = args[0]
        to_email = args[1] if len(args) > 1 else kwargs.get("to_email")
        subject = args[2] if len(args) > 2 else kwargs.get("subject")
        body = args[3] if len(args) > 3 else kwargs.get("body")
    else:
        # Signature 2: send_email(to_email, subject, body)
        to_email = args[0] if len(args) > 0 else kwargs.get("to_email")
        subject = args[1] if len(args) > 1 else kwargs.get("subject")
        body = args[2] if len(args) > 2 else kwargs.get("body")
        db = args[3] if len(args) > 3 else kwargs.get("db")

    # Ensure a local db session is created if none was passed
    db_created = False
    if db is None:
        db = SessionLocal()
        db_created = True

    # Validate recipient email format
    if not to_email or "@" not in to_email or "." not in to_email:
        err_msg = f"Invalid recipient email format: {to_email}"
        print(f"[DEBUG] Validation Failed - {err_msg}")
        if db_created:
            db.close()
        raise_on_error = kwargs.get("raise_on_error", False)
        if raise_on_error:
            raise ValueError(err_msg)
        return False

    SMTP_FROM_EMAIL = settings.SMTP_FROM_EMAIL
    recipient_email = to_email

    # Debug logs prior to sending attempt
    print("Sending email from:", SMTP_FROM_EMAIL)
    print("Sending email to:", recipient_email)
    print(f"[DEBUG] SMTP User: {settings.SMTP_USER}")
    print(f"[DEBUG] Subject: {subject}")

    # Safety Check: Never use SMTP_USER or SMTP_FROM_EMAIL as a recipient, never hardcode admin email
    blocked_recipients = {settings.SMTP_USER.lower(), settings.SMTP_FROM_EMAIL.lower(), "admin@phintra.com"}
    if recipient_email.lower() in blocked_recipients:
        err_msg = f"Delivery blocked: recipient {recipient_email} matches admin/sender credentials."
        print(f"[DEBUG] Safety Block - {err_msg}")
        if db_created:
            db.close()
        raise_on_error = kwargs.get("raise_on_error", False)
        if raise_on_error:
            raise ValueError(err_msg)
        return False

    # Verify it is safe awareness/training
    safe_disclaimer = "\n\n---\nDisclaimer: This is an educational notification or authorized security training communication from the Phintra Platform. Never share passwords or click links from unknown sources."
    full_body = body + safe_disclaimer

    # Determine the display From header — may be overridden by a sender profile
    sender_profile_id = kwargs.get("sender_profile_id")
    display_from = SMTP_FROM_EMAIL
    if sender_profile_id:
        try:
            from app.models.sender_profile import SenderProfile
            sp = db.query(SenderProfile).filter(SenderProfile.profile_id == sender_profile_id).first()
            if sp:
                display_from = f"{sp.display_name} <{sp.email_address}>"
        except Exception:
            pass  # Fallback to real SMTP from

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = display_from
    msg["To"] = recipient_email
    
    # If the body is HTML, we should add an alternative text/html representation
    if "html" in full_body.lower() or "<" in full_body:
        msg.set_content(full_body) # Plaintext fallback
        msg.add_alternative(full_body, subtype="html")
    else:
        msg.set_content(full_body)

    campaign_id = kwargs.get("campaign_id")
    template_id = kwargs.get("template_id")
    employee_id = kwargs.get("employee_id")
    log_entry = EmailLog(recipient_email=recipient_email, subject=subject, campaign_id=campaign_id, template_id=template_id, employee_id=employee_id)
    raise_on_error = kwargs.get("raise_on_error", False)

    try:
        # Check if settings are missing
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            # SMTP not configured - simulate sending by writing to console / logs
            print(f"[SMTP SIMULATION] Sent to: {recipient_email} | Subject: {subject}")
            log_entry.status = "Sent"
            log_entry.error_message = "Simulated delivery (SMTP Host/User not configured in .env)"
            db.add(log_entry)
            db.commit()
            print(f"[DEBUG] Send Status: success | Recipient: {recipient_email}")
            return True

        # Send email
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, [recipient_email], msg.as_string())
        server.quit()

        log_entry.status = "Sent"
        db.add(log_entry)
        db.commit()
        print(f"[DEBUG] Send Status: success | Recipient: {recipient_email}")
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"[SMTP ERROR] Failed to send email to {recipient_email}: {error_msg}")
        log_entry.status = "Failed"
        log_entry.error_message = error_msg
        db.add(log_entry)
        db.commit()
        print(f"[DEBUG] Send Status: failure | Recipient: {recipient_email} | Error: {error_msg}")
        if raise_on_error:
            raise e
        return False
    finally:
        if db_created:
            db.close()
