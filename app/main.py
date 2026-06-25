from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import (
    auth_router, users_router, employees_router, departments_router,
    campaigns_router, training_router, quizzes_router, certificates_router,
    emails_router, analytics_router, notifications_router, audit_logs_router,
    companies_router, ai_assistant_router, messages_router, leaderboard_router,
    gmail_router, sender_profiles_router
)

# Startup schema validation utility
def validate_db_schema():
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # 1. Validate companies table columns
    companies_columns = {col['name'] for col in inspector.get_columns('companies')}
    required_companies = {'id', 'company_name', 'company_email', 'company_address', 'created_at', 'admin_id'}
    missing_companies = required_companies - companies_columns
    if missing_companies:
        raise ValueError(f"Database schema mismatch: 'companies' table is missing columns {missing_companies}")
        
    # 2. Validate departments table columns
    departments_columns = {col['name'] for col in inspector.get_columns('departments')}
    required_departments = {'id', 'name', 'company_id', 'admin_id'}
    missing_departments = required_departments - departments_columns
    if missing_departments:
        raise ValueError(f"Database schema mismatch: 'departments' table is missing columns {missing_departments}")

    # 3. Validate employees table columns
    employees_columns = {col['name'] for col in inspector.get_columns('employees')}
    required_employees = {'id', 'first_name', 'last_name', 'email', 'company_id', 'department_id', 'admin_id'}
    missing_employees = required_employees - employees_columns
    if missing_employees:
        raise ValueError(f"Database schema mismatch: 'employees' table is missing columns {missing_employees}")
        
    print("[INFO] Database schema validation succeeded. All required tables and columns are present.")

# Create tables and execute migrations
try:
    # We make sure dependencies are imported before create_all
    from app.models.training import TrainingModule, TrainingAssignment, TrainingCompletion
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
        
    def run_migration_sql(sql_str: str, log_msg: str = None):
        try:
            with engine.begin() as conn:
                conn.execute(text(sql_str))
                if log_msg:
                    print(log_msg)
        except Exception:
            pass

    # 1. Create companies table if it doesn't exist
    run_migration_sql("""
        CREATE TABLE IF NOT EXISTS companies (
            id UUID PRIMARY KEY,
            company_name VARCHAR UNIQUE NOT NULL,
            company_email VARCHAR,
            company_address VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    # Alter companies
    run_migration_sql("ALTER TABLE companies ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to companies table.")
    run_migration_sql("ALTER TABLE companies ADD COLUMN company_email VARCHAR;")
    run_migration_sql("ALTER TABLE companies ADD COLUMN company_address VARCHAR;")
    run_migration_sql("ALTER TABLE companies ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();")

    # Alter departments
    run_migration_sql("ALTER TABLE departments ADD COLUMN company_id UUID REFERENCES companies(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE departments ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to departments table.")

    # Alter employees
    run_migration_sql("ALTER TABLE employees ADD COLUMN company_id UUID REFERENCES companies(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE employees ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to employees table.")
    run_migration_sql("ALTER TABLE employees ADD COLUMN dashboard_token VARCHAR;")
    run_migration_sql("ALTER TABLE employees ADD COLUMN dashboard_token_expires_at TIMESTAMP WITH TIME ZONE;")

    # Alter employees unique constraint
    run_migration_sql("ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_email_key;", "[INFO] Dropped global unique constraint employees_email_key.")
    run_migration_sql("DROP INDEX IF EXISTS uq_employees_email;", "[INFO] Dropped global unique index uq_employees_email.")

    # Create sender_profiles table
    run_migration_sql("""
        CREATE TABLE IF NOT EXISTS sender_profiles (
            profile_id UUID PRIMARY KEY,
            domain VARCHAR NOT NULL,
            email_address VARCHAR UNIQUE NOT NULL,
            display_name VARCHAR NOT NULL,
            company_name VARCHAR,
            department VARCHAR
        );
    """, "[INFO] Created sender_profiles table.")

    # Alter campaigns
    run_migration_sql("ALTER TABLE campaigns ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to campaigns table.")
    run_migration_sql("ALTER TABLE campaigns ADD COLUMN sender_profile_id UUID REFERENCES sender_profiles(profile_id) ON DELETE SET NULL;", "[INFO] Added sender_profile_id column to campaigns table.")

    # Alter email_templates
    run_migration_sql("ALTER TABLE email_templates ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to email_templates table.")
    run_migration_sql("ALTER TABLE email_templates ADD COLUMN difficulty VARCHAR DEFAULT 'Medium';")
    run_migration_sql("ALTER TABLE email_templates ADD COLUMN sender_name VARCHAR DEFAULT 'System Notification';")
    run_migration_sql("ALTER TABLE email_templates ADD COLUMN body_text VARCHAR;")
    run_migration_sql("ALTER TABLE email_templates ADD COLUMN sender_email VARCHAR;")

    # Alter email_logs
    run_migration_sql("ALTER TABLE email_logs ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to email_logs table.")

    # Alter reported_emails
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to reported_emails table.")

    # Alter quizzes
    run_migration_sql("ALTER TABLE quizzes ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to quizzes table.")

    # Alter certificates
    run_migration_sql("ALTER TABLE certificates ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;", "[INFO] Added admin_id column to certificates table.")

    # Alter training_modules
    run_migration_sql("ALTER TABLE training_modules ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE training_modules ADD COLUMN category VARCHAR;")
    run_migration_sql("ALTER TABLE training_modules ADD COLUMN duration INTEGER DEFAULT 10;")
    run_migration_sql("ALTER TABLE training_modules ADD COLUMN difficulty VARCHAR;")
    run_migration_sql("ALTER TABLE training_modules ADD COLUMN video_url VARCHAR;")
    run_migration_sql("ALTER TABLE training_modules ADD COLUMN uploaded_video_url VARCHAR;")

    # Alter training_assignments
    run_migration_sql("ALTER TABLE training_assignments ADD COLUMN admin_id UUID REFERENCES users(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE training_assignments ADD COLUMN department_id UUID REFERENCES departments(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE training_assignments ADD COLUMN company_id UUID REFERENCES companies(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE training_assignments ALTER COLUMN employee_id DROP NOT NULL;")

    # Alter campaign_recipients to add tracking, metrics, and isolation fields
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS admin_id UUID REFERENCES users(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments(id) ON DELETE CASCADE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS email_log_id UUID REFERENCES email_logs(id) ON DELETE SET NULL;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS opened_at TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS clicked_at TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS reported_at TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS training_completed_at TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE campaign_recipients ADD COLUMN IF NOT EXISTS quiz_completed_at TIMESTAMP WITH TIME ZONE;")

    # Create employee_activity_events table
    run_migration_sql("""
        CREATE TABLE IF NOT EXISTS employee_activity_events (
            id UUID PRIMARY KEY,
            admin_id UUID REFERENCES users(id) ON DELETE CASCADE,
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            department_id UUID REFERENCES departments(id) ON DELETE CASCADE,
            employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
            event_type VARCHAR NOT NULL,
            event_value VARCHAR,
            points_change INTEGER DEFAULT 0 NOT NULL,
            risk_change INTEGER DEFAULT 0 NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """, "[INFO] Created employee_activity_events table.")

    # 1b. Create report_logs table if it doesn't exist
    run_migration_sql("""
        CREATE TABLE IF NOT EXISTS report_logs (
            id UUID PRIMARY KEY,
            employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            action VARCHAR NOT NULL,
            reported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create training_completions table if it doesn't exist
    run_migration_sql("""
        CREATE TABLE IF NOT EXISTS training_completions (
            id UUID PRIMARY KEY,
            training_module_id UUID NOT NULL REFERENCES training_modules(id) ON DELETE CASCADE,
            employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            status VARCHAR NOT NULL DEFAULT 'not_started',
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create messages table if it doesn't exist
    run_migration_sql("""
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY,
            employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            admin_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            sender_id UUID NOT NULL,
            sender_role VARCHAR NOT NULL,
            sender_name VARCHAR NOT NULL,
            message_text TEXT NOT NULL,
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Ensure messages table has reported_email_id
    run_migration_sql("ALTER TABLE messages ADD COLUMN reported_email_id UUID REFERENCES reported_emails(id) ON DELETE CASCADE;")

    # Ensure all reported_emails columns are altered/added
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN email_sender VARCHAR;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN sender_email VARCHAR;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN email_body TEXT;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN threat_score INTEGER;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN report_reason VARCHAR;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN report_status VARCHAR DEFAULT 'Pending';")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN reviewed_at TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN department_id UUID REFERENCES departments(id) ON DELETE SET NULL;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN report_source VARCHAR DEFAULT 'direct';")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN message_id VARCHAR;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN thread_id VARCHAR;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN reported_by UUID REFERENCES users(id) ON DELETE SET NULL;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN subject VARCHAR;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN sender VARCHAR;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN email_date TIMESTAMP WITH TIME ZONE;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN risk_score INTEGER DEFAULT 0;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN risk_level VARCHAR DEFAULT 'Low';")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN status VARCHAR DEFAULT 'Pending';")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN analysis_results JSON;")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();")
    run_migration_sql("ALTER TABLE reported_emails ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE;")

    # Seed default company and backfill admins
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

        # Backfill admin_id for existing records in all tables using the first admin in users
        admin_row = conn.execute(text("SELECT id FROM users WHERE role = 'Admin' OR role = 'admin' LIMIT 1;")).fetchone()
        if admin_row:
            admin_id = admin_row[0]
            # Perform backfill
            conn.execute(text("UPDATE employees SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE companies SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE departments SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE campaigns SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE email_templates SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE email_logs SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE reported_emails SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE training_modules SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE quizzes SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE certificates SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})
            conn.execute(text("UPDATE training_assignments SET admin_id = :admin_id WHERE admin_id IS NULL;"), {"admin_id": admin_id})

        # Seed predefined sender profiles
        res_sp = conn.execute(text("SELECT COUNT(*) FROM sender_profiles;")).fetchone()
        if res_sp and res_sp[0] == 0:
            import uuid
            profiles = [
                {
                    "profile_id": str(uuid.uuid4()),
                    "display_name": "Security Update",
                    "email_address": "security-update@account-review-mail.com",
                    "domain": "account-review-mail.com",
                    "company_name": "Security Operations",
                    "department": "Security"
                },
                {
                    "profile_id": str(uuid.uuid4()),
                    "display_name": "HR Support",
                    "email_address": "hr-support@employee-benefits-mail.com",
                    "domain": "employee-benefits-mail.com",
                    "company_name": "Human Resources",
                    "department": "HR"
                },
                {
                    "profile_id": str(uuid.uuid4()),
                    "display_name": "Access Center Notifications",
                    "email_address": "notifications@secure-access-center.com",
                    "domain": "secure-access-center.com",
                    "company_name": "IT Helpdesk",
                    "department": "IT"
                },
                {
                    "profile_id": str(uuid.uuid4()),
                    "display_name": "Payroll Center",
                    "email_address": "payroll@salary-review-center.com",
                    "domain": "salary-review-center.com",
                    "company_name": "Finance Dept",
                    "department": "Payroll"
                },
                {
                    "profile_id": str(uuid.uuid4()),
                    "display_name": "Microsoft Auth Verification",
                    "email_address": "verify@login.microsoft-auth-verify.com",
                    "domain": "login.microsoft-auth-verify.com",
                    "company_name": "Microsoft Authentication",
                    "department": "IT Security"
                }
            ]
            for p in profiles:
                conn.execute(text("""
                    INSERT INTO sender_profiles (profile_id, domain, email_address, display_name, company_name, department)
                    VALUES (:profile_id, :domain, :email_address, :display_name, :company_name, :department)
                """), p)
            print("[INFO] Seeded predefined sender profiles.")

    # Run startup schema validation
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
app.include_router(ai_assistant_router)
app.include_router(messages_router)
app.include_router(leaderboard_router)
app.include_router(gmail_router)
app.include_router(sender_profiles_router)

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


