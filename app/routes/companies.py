from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.company import Company
from app.schemas.company_schema import CompanyCreate, CompanyUpdate, CompanyResponse
from app.dependencies import get_current_user
from app.models.user import User
from uuid import UUID
from typing import List

router = APIRouter(prefix="/companies", tags=["Companies"])

def get_admin_id(user: User) -> UUID:
    if user.role == "Admin" or user.role == "admin":
        return user.id
    return user.admin_id

@router.get("", response_model=List[CompanyResponse])
def list_companies(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all companies for the current admin."""
    admin_id = get_admin_id(current_user)
    return db.query(Company).filter(Company.admin_id == admin_id).all()

@router.get("/{id}", response_model=CompanyResponse)
def get_company(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get single company details."""
    admin_id = get_admin_id(current_user)
    company = db.query(Company).filter(Company.id == id, Company.admin_id == admin_id).first()
    if not company:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this company")
    return company

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(company_in: CompanyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Add a new company (Admins)."""
    if current_user.role not in ["Admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    admin_id = get_admin_id(current_user)
    
    if not company_in.company_name or not company_in.company_name.strip():
        raise HTTPException(status_code=400, detail="Company name cannot be empty")
        
    existing = db.query(Company).filter(
        Company.company_name == company_in.company_name.strip(),
        Company.admin_id == admin_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company with this name already exists")
        
    db_company = Company(
        company_name=company_in.company_name.strip(),
        company_email=company_in.company_email,
        company_address=company_in.company_address,
        admin_id=admin_id
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

@router.put("/{id}", response_model=CompanyResponse)
def update_company(id: UUID, company_in: CompanyUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update company details."""
    if current_user.role not in ["Admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    admin_id = get_admin_id(current_user)
    
    company = db.query(Company).filter(Company.id == id, Company.admin_id == admin_id).first()
    if not company:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this company")
        
    update_data = company_in.dict(exclude_unset=True)
    if "company_name" in update_data and update_data["company_name"]:
        company_name = update_data["company_name"].strip()
        if company_name != company.company_name:
            existing = db.query(Company).filter(
                Company.company_name == company_name,
                Company.admin_id == admin_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Company with this name already exists")
            company.company_name = company_name
            
    if "company_email" in update_data:
        company.company_email = update_data["company_email"]
    if "company_address" in update_data:
        company.company_address = update_data["company_address"]
        
    db.commit()
    db.refresh(company)
    return company

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_company(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a company."""
    if current_user.role not in ["Admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    admin_id = get_admin_id(current_user)
    
    company = db.query(Company).filter(Company.id == id, Company.admin_id == admin_id).first()
    if not company:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this company")
        
    db.delete(company)
    db.commit()
    return {"detail": "Company successfully deleted"}
