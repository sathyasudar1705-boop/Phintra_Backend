from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.quiz import Quiz, QuizQuestion, QuizAttempt
from app.models.training import TrainingModule, TrainingAssignment
from app.models.employee import Employee
from app.models.certificate import Certificate, Reward
from app.models.user import User
from app.schemas.quiz_schema import (
    QuizCreate, QuizResponse, QuizQuestionCreate, QuizQuestionResponse,
    QuizAttemptResponse, QuizAttemptSubmit
)
from app.dependencies import require_manager, require_employee, get_user_admin_id
from uuid import UUID
from datetime import datetime
import secrets
from typing import List

router = APIRouter(tags=["Quizzes"])

@router.get("/quizzes", response_model=List[QuizResponse])
def list_quizzes(db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """List all configured training module quizzes (Employees, Managers, Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    return db.query(Quiz).join(TrainingModule).filter(
        (Quiz.admin_id == admin_id) | (TrainingModule.admin_id == admin_id)
    ).all()

@router.post("/quizzes", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def create_quiz(quiz_in: QuizCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Create a new quiz for a training module (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    
    # Verify module exists and belongs to this workspace admin
    mod = db.query(TrainingModule).filter(
        TrainingModule.id == quiz_in.module_id,
        TrainingModule.admin_id == admin_id
    ).first()
    if not mod:
        raise HTTPException(status_code=400, detail="Training module does not exist or access denied")
        
    db_quiz = Quiz(module_id=quiz_in.module_id, passing_score=quiz_in.passing_score, admin_id=admin_id)
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

@router.post("/quizzes/{id}/questions", response_model=QuizQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_quiz_question(id: UUID, ques_in: QuizQuestionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Add a question block to a quiz (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    quiz = db.query(Quiz).join(TrainingModule).filter(
        Quiz.id == id,
        (Quiz.admin_id == admin_id) | (TrainingModule.admin_id == admin_id)
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or access denied")
        
    db_ques = QuizQuestion(
        quiz_id=id,
        question_text=ques_in.question_text,
        options=ques_in.options,
        correct_option_index=ques_in.correct_option_index
    )
    db.add(db_ques)
    db.commit()
    db.refresh(db_ques)
    return db_ques

@router.post("/quizzes/{id}/attempt", response_model=QuizAttemptResponse)
def submit_quiz_attempt(id: UUID, attempt_in: QuizAttemptSubmit, db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """Record an employee's quiz answers, calculate score, and award certificates/XP if passed (Employees, Managers, Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    quiz = db.query(Quiz).join(TrainingModule).filter(
        Quiz.id == id,
        (Quiz.admin_id == admin_id) | (TrainingModule.admin_id == admin_id)
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or access denied")
        
    emp = db.query(Employee).filter(Employee.id == attempt_in.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == id).order_by(QuizQuestion.created_at.asc()).all()
    if not questions:
        raise HTTPException(status_code=400, detail="This quiz has no questions compiled yet")
        
    if len(attempt_in.answers) != len(questions):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid answers count. Expected {len(questions)} answers, got {len(attempt_in.answers)}"
        )
        
    # Evaluate answers
    correct_count = 0
    for idx, question in enumerate(questions):
        user_answer = attempt_in.answers[idx]
        if user_answer == question.correct_option_index:
            correct_count += 1
            
    score = int((correct_count / len(questions)) * 100)
    passed = score >= quiz.passing_score
    
    # Store attempt
    attempt = QuizAttempt(
        employee_id=emp.id,
        quiz_id=quiz.id,
        score=score,
        passed=passed
    )
    db.add(attempt)

    from app.utils.scoring import log_activity_event
    from app.models.campaign import CampaignRecipient

    # Update recipient quiz completion
    recipient = db.query(CampaignRecipient).filter(
        CampaignRecipient.employee_id == emp.id
    ).order_by(CampaignRecipient.created_at.desc()).first()
    if recipient:
        recipient.quiz_completed_at = datetime.utcnow()
        if passed:
            recipient.status = "Completed Training"
        else:
            recipient.status = "Failed"

    if passed:
        log_activity_event(db, emp.id, "quiz_passed", event_value=str(quiz.id))
    else:
        log_activity_event(db, emp.id, "quiz_failed", event_value=str(quiz.id))

    # If passed, complete training module and award certificate
    if passed:
        assignment = db.query(TrainingAssignment).filter(
            TrainingAssignment.employee_id == emp.id,
            TrainingAssignment.module_id == quiz.module_id
        ).first()
        
        # Create assignment if it didn't exist
        if not assignment:
            assignment = TrainingAssignment(
                employee_id=emp.id,
                module_id=quiz.module_id,
                progress=100,
                completed=True,
                completed_at=datetime.utcnow()
            )
            db.add(assignment)
        else:
            if not assignment.completed:
                assignment.progress = 100
                assignment.completed = True
                assignment.completed_at = datetime.utcnow()
                
        # Award XP reward
        mod = db.query(TrainingModule).filter(TrainingModule.id == quiz.module_id).first()
        xp_amount = mod.xp_reward if mod else 100
        
        # Check if already rewarded to prevent double XP
        prev_reward = db.query(Reward).filter(
            Reward.employee_id == emp.id,
            Reward.description.ilike(f"%Completed {mod.title}%")
        ).first()
        
        if not prev_reward:
            reward = Reward(
                employee_id=emp.id,
                xp_amount=xp_amount,
                description=f"Completed {mod.title if mod else 'Training'} assessment"
            )
            db.add(reward)
            
            # Reduce risk rating on employee
            emp.risk_score = max(0.0, emp.risk_score - 10.0)
            if emp.risk_score < 20.0:
                emp.status = "Low Risk"
            elif emp.risk_score < 50.0:
                emp.status = "Medium Risk"
                
        # Issue Certificate if not already issued
        prev_cert = db.query(Certificate).filter(
            Certificate.employee_id == emp.id,
            Certificate.module_id == quiz.module_id
        ).first()
        
        if not prev_cert:
            ver_code = f"PHN-{secrets.token_hex(4).upper()}"
            cert = Certificate(
                employee_id=emp.id,
                module_id=quiz.module_id,
                verification_code=ver_code
            )
            db.add(cert)
            
    db.commit()
    db.refresh(attempt)
    return attempt
