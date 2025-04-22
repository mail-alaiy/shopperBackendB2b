from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# Load parts from .env
DB_HOST = os.getenv("DB_HOST_SQL")
DB_PORT = os.getenv("DB_PORT_SQL")
DB_NAME = os.getenv("DB_NAME_SQL")
DB_USER = os.getenv("DB_USER_NAME_SQL")
DB_PASSWORD = os.getenv("DB_PASSWORD_SQL")

# Build the full DATABASE_URL string
DATABASE_URL = f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
