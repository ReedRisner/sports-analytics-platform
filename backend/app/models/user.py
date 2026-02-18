# backend/app/models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, text
from datetime import datetime

from app.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    tier = Column(String, default="free", nullable=False)  # free, premium, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )
    


"""
DATABASE SETUP:

Option 1 - Using Alembic (Recommended):
1. alembic revision --autogenerate -m "add users table"
2. alembic upgrade head

Option 2 - Manual SQL:
Run this in your PostgreSQL database:

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    hashed_password VARCHAR NOT NULL,
    tier VARCHAR DEFAULT 'free' NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- Verify it was created:
\dt
\d users
"""