from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.certificate import Certificate
from app.models.employee import Employee
from app.models.training import TrainingModule
from app.models.user import User
from app.schemas.certificate_schema import CertificateCreate, CertificateResponse
from app.dependencies import require_manager, require_employee
from uuid import UUID
import secrets
from typing import List

router = APIRouter(prefix="/certificates", tags=["Certificates"])

@router.get("", response_model=List[CertificateResponse])
def list_certificates(db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """List all verified credentials certificates (Employees, Managers, Admins)."""
    return db.query(Certificate).all()

@router.post("", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
def issue_certificate(req: CertificateCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Manually issue a training certificate (Managers & Admins)."""
    # Verify employee and module exist
    emp = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not emp:
        raise HTTPException(status_code=400, detail="Employee does not exist")
        
    mod = db.query(TrainingModule).filter(TrainingModule.id == req.module_id).first()
    if not mod:
        raise HTTPException(status_code=400, detail="Training module does not exist")
        
    # Check if already issued
    existing = db.query(Certificate).filter(
        Certificate.employee_id == req.employee_id,
        Certificate.module_id == req.module_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Certificate already issued to this employee for this module")
        
    ver_code = f"PHN-MAN-{secrets.token_hex(4).upper()}"
    db_cert = Certificate(
        employee_id=req.employee_id,
        module_id=req.module_id,
        verification_code=ver_code
    )
    db.add(db_cert)
    db.commit()
    db.refresh(db_cert)
    return db_cert

from app.config import settings

@router.get("/{id}/download")
def download_certificate(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """Download certificate metadata (Employees, Managers, Admins)."""
    cert = db.query(Certificate).filter(Certificate.id == id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
        
    emp = db.query(Employee).filter(Employee.id == cert.employee_id).first()
    mod = db.query(TrainingModule).filter(TrainingModule.id == cert.module_id).first()
    
    return {
        "certificate_id": str(cert.id),
        "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "Unknown Employee",
        "employee_email": emp.email if emp else "Unknown Email",
        "module_title": mod.title if mod else "Unknown Module",
        "verification_code": cert.verification_code,
        "issued_at": cert.issued_at.isoformat(),
        "download_url": f"{settings.FRONTEND_URL}/api/certificates/{cert.id}/download"
    }
