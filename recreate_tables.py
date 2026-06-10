import os
from sqlalchemy import create_engine, text
from app.database import Base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/phintra")

def recreate():
    print("Recreating database tables...")
    engine = create_engine(DATABASE_URL)
    
    # Import all models to ensure they are registered
    import app.models
    
    # Cascade drop all tables
    tables = [
        "audit_logs", "notifications", "security_scores", "rewards", "reported_emails",
        "certificates", "quiz_attempts", "quiz_questions", "quizzes", "training_assignments",
        "training_modules", "campaign_clicks", "campaign_recipients", "campaigns", "email_logs", "employees",
        "departments", "users", "threat_feed", "email_templates", "awareness_pages"
    ]
    
    with engine.connect() as conn:
        for t in tables:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE;"))
                print(f"Dropped table {t}")
            except Exception as e:
                print(f"Error dropping {t}: {e}")
        conn.commit()
        
    Base.metadata.create_all(bind=engine)
    print("Created all tables with the current schemas.")

if __name__ == "__main__":
    recreate()
