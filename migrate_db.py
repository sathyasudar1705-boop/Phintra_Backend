import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/phintra")

def run_migrations():
    print(f"Connecting to database to check/alter tables...")
    engine = create_engine(DATABASE_URL)
    
    # 1. employees.password_hash
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE employees ADD COLUMN password_hash VARCHAR;"))
            conn.commit()
            print("Added employees.password_hash column.")
        except Exception as e:
            print("employees.password_hash column skip/exists:", e)
            
    # 2. employees.created_by
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE employees ADD COLUMN created_by UUID;"))
            conn.commit()
            print("Added employees.created_by column.")
        except Exception as e:
            print("employees.created_by column skip/exists:", e)

    # 3. employees.is_active
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE employees ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;"))
            conn.commit()
            print("Added employees.is_active column.")
        except Exception as e:
            print("employees.is_active column skip/exists:", e)

    # 4. email_logs.employee_id
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE email_logs ADD COLUMN employee_id UUID;"))
            conn.commit()
            print("Added email_logs.employee_id column.")
        except Exception as e:
            print("email_logs.employee_id column skip/exists:", e)

    # 5. email_templates.category
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE email_templates ADD COLUMN category VARCHAR DEFAULT 'Phishing';"))
            conn.commit()
            print("Added email_templates.category column.")
        except Exception as e:
            print("email_templates.category column skip/exists:", e)

    # 6. reported_emails columns and constraints
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE reported_emails ALTER COLUMN employee_id DROP NOT NULL;"))
            conn.commit()
            print("Made reported_emails.employee_id column nullable.")
        except Exception as e:
            print("reported_emails.employee_id column nullable skip/exists:", e)
            
    # Make subject and sender nullable for backward compatibility
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE reported_emails ALTER COLUMN subject DROP NOT NULL;"))
            conn.commit()
        except Exception as e:
            print("subject column alter skip:", e)
        try:
            conn.execute(text("ALTER TABLE reported_emails ALTER COLUMN sender DROP NOT NULL;"))
            conn.commit()
        except Exception as e:
            print("sender column alter skip:", e)

    columns_to_add = [
        ("reported_by", "UUID"),
        ("email_date", "TIMESTAMP WITH TIME ZONE"),
        ("email_body", "VARCHAR"),
        ("risk_score", "INTEGER NOT NULL DEFAULT 0"),
        ("risk_level", "VARCHAR NOT NULL DEFAULT 'Low'"),
        ("report_status", "VARCHAR NOT NULL DEFAULT 'Pending'"),
        ("created_at", "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("analysis_results", "JSON"),
        ("employee_name", "VARCHAR"),
        ("employee_email", "VARCHAR"),
        ("campaign_id", "UUID"),
        ("campaign_name", "VARCHAR"),
        ("email_subject", "VARCHAR"),
        ("email_sender", "VARCHAR"),
        ("report_reason", "VARCHAR"),
        ("reviewed_at", "TIMESTAMP WITH TIME ZONE"),
        ("reviewed_by", "UUID")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE reported_emails ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            print(f"Added reported_emails.{col_name} column.")
        except Exception as e:
            print(f"reported_emails.{col_name} column skip/exists")
            
    # 7. employees new columns (name, role, hashed_password) and constraints
    emp_cols = [
        ("name", "VARCHAR"),
        ("role", "VARCHAR DEFAULT 'employee'"),
        ("hashed_password", "VARCHAR")
    ]
    for col_name, col_type in emp_cols:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            print(f"Added employees.{col_name} column.")
        except Exception as e:
            print(f"employees.{col_name} column skip/exists: {e}")

    # Backfill name, role, and hashed_password for employees
    with engine.connect() as conn:
        try:
            conn.execute(text("UPDATE employees SET name = TRIM(first_name || ' ' || last_name) WHERE name IS NULL;"))
            conn.execute(text("UPDATE employees SET role = 'employee' WHERE role IS NULL;"))
            conn.execute(text("UPDATE employees SET hashed_password = password_hash WHERE hashed_password IS NULL;"))
            conn.commit()
            print("Backfilled employees name, role, and hashed_password.")
        except Exception as e:
            print("Error backfilling employees:", e)

    # Add unique constraint to employees.email
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE employees ADD CONSTRAINT employees_email_key UNIQUE (email);"))
            conn.commit()
            print("Added unique constraint employees_email_key to email.")
        except Exception as e:
            print("employees_email_key constraint skip/exists: (likely already unique or constraint exists)")
                
    print("Database check and alterations completed.")

if __name__ == "__main__":
    run_migrations()
