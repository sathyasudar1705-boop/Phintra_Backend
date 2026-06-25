from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.sender_profile import SenderProfile
from app.models.user import User
from app.dependencies import require_manager, require_admin, get_user_admin_id

router = APIRouter(prefix="/sender-profiles", tags=["Sender Profiles"])


@router.get("", response_model=List[dict])
def list_sender_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """List all available sender profiles visible to this admin (Managers & Admins)."""
    profiles = db.query(SenderProfile).all()
    return [
        {
            "profile_id": str(p.profile_id),
            "domain": p.domain,
            "email_address": p.email_address,
            "display_name": p.display_name,
            "company_name": p.company_name,
            "department": p.department
        }
        for p in profiles
    ]


@router.get("/{profile_id}", response_model=dict)
def get_sender_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Retrieve a single sender profile by ID (Managers & Admins)."""
    profile = db.query(SenderProfile).filter(SenderProfile.profile_id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Sender profile not found")
    return {
        "profile_id": str(profile.profile_id),
        "domain": profile.domain,
        "email_address": profile.email_address,
        "display_name": profile.display_name,
        "company_name": profile.company_name,
        "department": profile.department
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_sender_profile(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new realistic sender profile for phishing simulations (Admins only)."""
    required = ["domain", "email_address", "display_name"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Prevent duplicate email_address
    existing = db.query(SenderProfile).filter(
        SenderProfile.email_address == payload["email_address"]
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A sender profile with this email address already exists")

    profile = SenderProfile(
        domain=payload["domain"],
        email_address=payload["email_address"],
        display_name=payload["display_name"],
        company_name=payload.get("company_name"),
        department=payload.get("department")
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {
        "profile_id": str(profile.profile_id),
        "domain": profile.domain,
        "email_address": profile.email_address,
        "display_name": profile.display_name,
        "company_name": profile.company_name,
        "department": profile.department
    }


@router.put("/{profile_id}", response_model=dict)
def update_sender_profile(
    profile_id: UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update an existing sender profile (Admins only)."""
    profile = db.query(SenderProfile).filter(SenderProfile.profile_id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Sender profile not found")

    updatable = ["domain", "email_address", "display_name", "company_name", "department"]
    for field in updatable:
        if field in payload:
            setattr(profile, field, payload[field])

    db.commit()
    db.refresh(profile)
    return {
        "profile_id": str(profile.profile_id),
        "domain": profile.domain,
        "email_address": profile.email_address,
        "display_name": profile.display_name,
        "company_name": profile.company_name,
        "department": profile.department
    }


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sender_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a sender profile (Admins only)."""
    profile = db.query(SenderProfile).filter(SenderProfile.profile_id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Sender profile not found")
    db.delete(profile)
    db.commit()
