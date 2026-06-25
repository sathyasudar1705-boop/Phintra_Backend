import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()
# Load .env from parent directories if not in current working directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/phintra")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkeythatisverysecureandlongerthan32characters")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "awareness@phintra.com")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://phintra-frontend.vercel.app")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")  # Add your Gemini API key

settings = Settings()
