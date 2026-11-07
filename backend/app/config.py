import os
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoLead AI"
    VERSION: str = "1.0.0"
    
    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Native Gmail Direct SMTP / IMAP Protocol (Google App Password)
    EMAIL_USER: str = os.getenv("EMAIL_USER", "")
    EMAIL_APP_PASSWORD: str = os.getenv("EMAIL_APP_PASSWORD", "")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    IMAP_HOST: str = os.getenv("IMAP_HOST", "imap.gmail.com")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    SENDER_NAME: str = os.getenv("SENDER_NAME", "Alex Rivera")
    
    # Pitch defaults
    PORTFOLIO_URL: str = os.getenv("PORTFOLIO_URL", "https://alexrivera.dev")
    CALENDLY_URL: str = os.getenv("CALENDLY_URL", "https://calendly.com/alexrivera/30min")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./autolead.db")
    
    # Auto Reply Mode: 'manual' or 'autonomous'
    AUTO_REPLY_MODE: str = os.getenv("AUTO_REPLY_MODE", "manual")

    # Fully Autonomous Outreach Pipeline (10:00 AM IST: Auto-Scrape -> Auto-Analyze -> Auto-Send via SMTP)
    AUTONOMOUS_OUTREACH: bool = os.getenv("AUTONOMOUS_OUTREACH", "true").lower() in ["true", "1", "yes"]
    RESPECT_TIMEZONE_WINDOW: bool = os.getenv("RESPECT_TIMEZONE_WINDOW", "false").lower() in ["true", "1", "yes"]
    
    # Anti-ban throttle & schedule
    DAILY_SCRAPE_TIME_IST: str = os.getenv("DAILY_SCRAPE_TIME_IST", "10:00")
    EMAIL_THROTTLE_MIN_SEC: int = int(os.getenv("EMAIL_THROTTLE_MIN_SEC", "45"))
    EMAIL_THROTTLE_MAX_SEC: int = int(os.getenv("EMAIL_THROTTLE_MAX_SEC", "90"))
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

