import os
import re
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

db_url = settings.DATABASE_URL.strip()

# If SQLite relative path, resolve to project root so running from / or /backend uses the exact same DB
if db_url.startswith("sqlite:///./"):
    filename = db_url.replace("sqlite:///./", "")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    abs_db_path = os.path.join(base_dir, filename)
    db_url = f"sqlite:///{abs_db_path}"

connect_args = {}

# Handle PostgreSQL URLs
if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
    # Ensure psycopg2 driver is used
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # Handle unencoded special characters like '@' in password:
    m = re.match(r"^(postgresql\+psycopg2://)([^:]+):(.*)@([^@/]+:\d+/[^?]+)(.*)$", db_url)
    if m:
        prefix, user, raw_pass, host_and_db, query = m.groups()
        encoded_pass = quote_plus(raw_pass) if "@" in raw_pass else raw_pass
        db_url = f"{prefix}{user}:{encoded_pass}@{host_and_db}{query}"

    # Supabase / cloud postgres requires SSL
    if "supabase.com" in db_url or "pooler.supabase.com" in db_url:
        connect_args["sslmode"] = "require"

elif db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
