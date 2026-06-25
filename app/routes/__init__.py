from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.employees import router as employees_router
from app.routes.departments import router as departments_router
from app.routes.campaigns import router as campaigns_router
from app.routes.training import router as training_router
from app.routes.quizzes import router as quizzes_router
from app.routes.certificates import router as certificates_router
from app.routes.emails import router as emails_router
from app.routes.analytics import router as analytics_router
from app.routes.notifications import router as notifications_router
from app.routes.audit_logs import router as audit_logs_router
from app.routes.companies import router as companies_router
from app.routes.ai_assistant import router as ai_assistant_router
from app.routes.messages import router as messages_router
from app.routes.leaderboard import router as leaderboard_router
from app.routes.gmail import router as gmail_router
from app.routes.sender_profiles import router as sender_profiles_router

__all__ = [
    "auth_router",
    "users_router",
    "employees_router",
    "departments_router",
    "campaigns_router",
    "training_router",
    "quizzes_router",
    "certificates_router",
    "emails_router",
    "analytics_router",
    "notifications_router",
    "audit_logs_router",
    "companies_router",
    "ai_assistant_router",
    "messages_router",
    "leaderboard_router",
    "gmail_router",
    "sender_profiles_router"
]
