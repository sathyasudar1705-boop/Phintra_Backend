from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import (
    auth_router, users_router, employees_router, departments_router,
    campaigns_router, training_router, quizzes_router, certificates_router,
    emails_router, analytics_router, notifications_router, audit_logs_router
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Phintra API",
    description="Production-ready FastAPI backend for Phintra cybersecurity awareness and training platform.",
    version="1.0.0"
)

# CORS
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8501",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8501",
    "https://phintra.vercel.app",
    "https://phintra-backend.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(employees_router)
app.include_router(departments_router)
app.include_router(campaigns_router)
app.include_router(training_router)
app.include_router(quizzes_router)
app.include_router(certificates_router)
app.include_router(emails_router)
app.include_router(analytics_router)
app.include_router(notifications_router)
app.include_router(audit_logs_router)

# Root endpoint
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Phintra Cybersecurity Platform API",
        "documentation": "/docs"
    }

# Gmail Add-on endpoint
@app.post("/report-email")
async def report_email(request: Request):
    data = await request.json()

    print("=" * 50)
    print("PHISHING EMAIL REPORTED")
    print("=" * 50)
    print(data)
    print("=" * 50)

    return {
        "status": "success",
        "message": "Email reported successfully",
        "email": data
    }


