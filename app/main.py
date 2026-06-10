from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import (
    auth_router, users_router, employees_router, departments_router,
    campaigns_router, training_router, quizzes_router, certificates_router,
    emails_router, analytics_router, notifications_router, audit_logs_router
)

# Create tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[WARNING] Database table creation failed on startup (db server may be unreachable/offline): {e}")

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
    "https://phintra-frontend.vercel.app",
    "https://phintra-backend.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers & Logging Middlewares
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"[DEBUG ERROR] Validation error on {request.method} {request.url.path}: {exc.errors()}")
    body_data = b""
    try:
        body_data = await request.body()
    except Exception:
        pass
    print(f"[DEBUG ERROR] Request body was: {body_data.decode('utf-8', errors='ignore')}")
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid request payload or query parameters.", "errors": exc.errors()}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    print(f"[DEBUG ERROR] HTTP exception on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    print(f"[DEBUG ERROR] Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

@app.middleware("http")
async def debug_logging_middleware(request: Request, call_next):
    # Log preflight/OPTIONS requests and authentication routes
    is_options = request.method == "OPTIONS"
    is_auth_route = "/auth/" in request.url.path
    
    if is_options or is_auth_route:
        print("=" * 60)
        print(f"[DEBUG REQUEST] {request.method} {request.url.path}")
        print(f"[DEBUG REQUEST] Headers: {dict(request.headers)}")
        print(f"[DEBUG REQUEST] Origin Header: {request.headers.get('origin')}")
        print("=" * 60)
        
    response = await call_next(request)
    
    if is_options or is_auth_route:
        print("=" * 60)
        print(f"[DEBUG RESPONSE] Status Code: {response.status_code}")
        print(f"[DEBUG RESPONSE] Headers: {dict(response.headers)}")
        print("=" * 60)
        
    return response

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


