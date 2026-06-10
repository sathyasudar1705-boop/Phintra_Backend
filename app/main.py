from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import (
    auth_router, users_router, employees_router, departments_router,
    campaigns_router, training_router, quizzes_router, certificates_router,
    emails_router, analytics_router, notifications_router, audit_logs_router,
    companies_router
)

# Startup schema validation utility
def validate_db_schema():
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # 1. Validate companies table columns
    companies_columns = {col['name'] for col in inspector.get_columns('companies')}
    required_companies = {'id', 'company_name', 'company_email', 'company_address', 'created_at'}
    missing_companies = required_companies - companies_columns
    if missing_companies:
        raise ValueError(f"Database schema mismatch: 'companies' table is missing columns {missing_companies}")
        
    # 2. Validate departments table columns
    departments_columns = {col['name'] for col in inspector.get_columns('departments')}
    required_departments = {'id', 'name', 'company_id'}
    missing_departments = required_departments - departments_columns
    if missing_departments:
        raise ValueError(f"Database schema mismatch: 'departments' table is missing columns {missing_departments}")

    # 3. Validate employees table columns
    employees_columns = {col['name'] for col in inspector.get_columns('employees')}
    required_employees = {'id', 'first_name', 'last_name', 'email', 'company_id', 'department_id'}
    missing_employees = required_employees - employees_columns
    if missing_employees:
        raise ValueError(f"Database schema mismatch: 'employees' table is missing columns {missing_employees}")
        
    print("[INFO] Database schema validation succeeded. All required tables and columns are present.")

# Create tables and execute migrations
try:
    Base.metadata.create_all(bind=engine)
    
    # Execute raw SQL migration checks to add columns/tables dynamically
    from sqlalchemy import text
    
    # 1. Create companies table if it doesn't exist
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS companies (
                id UUID PRIMARY KEY,
                company_name VARCHAR UNIQUE NOT NULL,
                company_email VARCHAR,
                company_address VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        
    # 1b. Add company_email, company_address, created_at columns to companies if not exist
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE companies ADD COLUMN company_email VARCHAR;"))
            print("[INFO] Added company_email column to companies table.")
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE companies ADD COLUMN company_address VARCHAR;"))
            print("[INFO] Added company_address column to companies table.")
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE companies ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
            print("[INFO] Added created_at column to companies table.")
    except Exception:
        pass
        
    # 2. Add company_id to departments if not exists
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE departments ADD COLUMN company_id UUID REFERENCES companies(id) ON DELETE CASCADE;"))
            print("[INFO] Added company_id column to departments table.")
    except Exception:
        pass
        
    # 3. Add company_id to employees if not exists
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE employees ADD COLUMN company_id UUID REFERENCES companies(id) ON DELETE CASCADE;"))
            print("[INFO] Added company_id column to employees table.")
    except Exception:
        pass

    # 4. Create report_logs table if it doesn't exist
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS report_logs (
                id UUID PRIMARY KEY,
                employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                action VARCHAR NOT NULL,
                reported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))

    # 5. Add difficulty and sender_name columns to email_templates if not exists
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE email_templates ADD COLUMN difficulty VARCHAR DEFAULT 'Medium';"))
            print("[INFO] Added difficulty column to email_templates table.")
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE email_templates ADD COLUMN sender_name VARCHAR DEFAULT 'System Notification';"))
            print("[INFO] Added sender_name column to email_templates table.")
    except Exception:
        pass

    # 6. Seed default company if empty
    with engine.begin() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM companies;")).fetchone()
        if res and res[0] == 0:
            import uuid
            default_company_id = uuid.uuid4()
            conn.execute(text("""
                INSERT INTO companies (id, company_name, company_email, company_address)
                VALUES (:id, 'Phintra Enterprise', 'admin@phintra.com', '123 Cyber Way')
            """), {"id": default_company_id})
            print("[INFO] Seeded default company 'Phintra Enterprise'.")
            
            # Link all existing departments to this default company
            conn.execute(text("UPDATE departments SET company_id = :id WHERE company_id IS NULL;"), {"id": default_company_id})
            # Link all existing employees to this default company
            conn.execute(text("UPDATE employees SET company_id = :id WHERE company_id IS NULL;"), {"id": default_company_id})
            
    # 7. Run startup schema validation
    validate_db_schema()
except Exception as e:
    print(f"[WARNING] Database table creation or startup migration failed: {e}")

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

from sqlalchemy.exc import ProgrammingError

@app.exception_handler(ProgrammingError)
async def programming_error_handler(request: Request, exc: ProgrammingError):
    error_msg = str(exc.orig) if exc.orig else str(exc)
    print(f"[DATABASE ERROR] Schema mismatch or query programming error: {error_msg}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Database schema mismatch. Please contact administrator to run database migrations.",
            "error_code": "DB_SCHEMA_MISMATCH",
            "message": error_msg
        }
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
app.include_router(companies_router)

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


