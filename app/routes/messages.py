from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.database import get_db
from app.models.message import Message
from app.models.employee import Employee
from app.models.department import Department
from app.models.user import User
from app.schemas.message_schema import MessageCreate, AdminMessageCreate, MessageRead, ThreadInfo
from app.dependencies import get_current_user, get_current_admin

router = APIRouter(prefix="/messages", tags=["Messages"])

@router.get("/thread", response_model=List[MessageRead])
def get_employee_thread(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve message history for the currently logged-in employee."""
    emp = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not emp:
        # Fallback to check by email if mock user id does not align directly
        emp = db.query(Employee).filter(Employee.email == current_user.email).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")

    if not emp.admin_id:
        raise HTTPException(status_code=400, detail="No security administrator is assigned to your account.")

    # Mark incoming admin messages as read
    db.query(Message).filter(
        Message.employee_id == emp.id,
        Message.admin_id == emp.admin_id,
        Message.sender_role == "admin",
        Message.is_read == False
    ).update({Message.is_read: True}, synchronize_session=False)
    db.commit()

    messages = db.query(Message).filter(
        Message.employee_id == emp.id,
        Message.admin_id == emp.admin_id
    ).order_by(Message.created_at.asc()).all()

    return messages

@router.post("/send", response_model=MessageRead)
def send_employee_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a support or security query message to the assigned administrator."""
    emp = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not emp:
        emp = db.query(Employee).filter(Employee.email == current_user.email).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")

    if not emp.admin_id:
        raise HTTPException(status_code=400, detail="No security administrator is assigned to your account.")

    db_msg = Message(
        employee_id=emp.id,
        admin_id=emp.admin_id,
        sender_id=emp.id,
        sender_role="employee",
        sender_name=emp.name or f"{emp.first_name} {emp.last_name}".strip() or "Employee",
        message_text=payload.message_text,
        is_read=False
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)

    return db_msg

@router.get("/admin/threads", response_model=List[ThreadInfo])
def get_admin_threads(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all active message threads for the logged-in administrator (Admins only)."""
    # Find all employees belonging to this admin
    employees = db.query(Employee).filter(Employee.admin_id == current_admin.id).all()
    emp_ids = [emp.id for emp in employees]

    if not emp_ids:
        return []

    # Get only employees who have at least one message
    employees_with_messages = db.query(Employee).join(
        Message, Employee.id == Message.employee_id
    ).filter(
        Employee.admin_id == current_admin.id
    ).distinct().all()

    threads = []
    for emp in employees_with_messages:
        # Get last message
        last_msg = db.query(Message).filter(
            Message.employee_id == emp.id,
            Message.admin_id == current_admin.id
        ).order_by(Message.created_at.desc()).first()

        # Get unread message count from this employee
        unread = db.query(Message).filter(
            Message.employee_id == emp.id,
            Message.admin_id == current_admin.id,
            Message.sender_role == "employee",
            Message.is_read == False
        ).count()

        # Get department name
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        dept_name = dept.name if dept else "General"

        threads.append(ThreadInfo(
            employee_id=emp.id,
            employee_name=emp.name or f"{emp.first_name} {emp.last_name}".strip() or "Employee",
            employee_email=emp.email,
            department_name=dept_name,
            last_message=last_msg.message_text if last_msg else "",
            last_message_at=last_msg.created_at if last_msg else emp.created_at,
            unread_count=unread
        ))

    # Sort threads: newest messages first
    threads.sort(key=lambda x: x.last_message_at, reverse=True)
    return threads

@router.get("/admin/thread/{employee_id}", response_model=List[MessageRead])
def get_admin_thread_messages(
    employee_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Retrieve full message history for a specific employee thread (Admins only)."""
    # Verify employee belongs to this admin
    emp = db.query(Employee).filter(Employee.id == employee_id, Employee.admin_id == current_admin.id).first()
    if not emp:
        raise HTTPException(status_code=403, detail="Access denied. Employee belongs to another administrator.")

    # Mark employee's incoming messages as read
    db.query(Message).filter(
        Message.employee_id == employee_id,
        Message.admin_id == current_admin.id,
        Message.sender_role == "employee",
        Message.is_read == False
    ).update({Message.is_read: True}, synchronize_session=False)
    db.commit()

    messages = db.query(Message).filter(
        Message.employee_id == employee_id,
        Message.admin_id == current_admin.id
    ).order_by(Message.created_at.asc()).all()

    return messages

@router.post("/admin/reply", response_model=MessageRead)
def send_admin_reply(
    payload: AdminMessageCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Send a reply message to a specific employee (Admins only)."""
    emp = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.admin_id == current_admin.id).first()
    if not emp:
        raise HTTPException(status_code=403, detail="Access denied. Employee belongs to another administrator.")

    db_msg = Message(
        employee_id=emp.id,
        admin_id=current_admin.id,
        sender_id=current_admin.id,
        sender_role="admin",
        sender_name=getattr(current_admin, "full_name", None) or current_admin.email or "Security Team",
        message_text=payload.message_text,
        is_read=False
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)

    return db_msg
