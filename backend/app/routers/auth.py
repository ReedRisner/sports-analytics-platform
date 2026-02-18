# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import secrets
import bcrypt

from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Pydantic Models ───────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Helper Functions ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(user_id: int) -> str:
    """Create a simple access token"""
    # Simple token for now - in production use JWT with expiry
    return f"token_{user_id}_{secrets.token_urlsafe(32)}"


# ── POST /auth/signup ─────────────────────────────────────────────────────────
@router.post("/signup", response_model=TokenResponse)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new user account and automatically log them in.
    No email verification required.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate password length
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Create user
    hashed_pw = hash_password(request.password)
    user = User(
        email=request.email,
        name=request.name,
        hashed_password=hashed_pw,
        tier="free",
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create access token and return
    token = create_access_token(user.id)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "tier": user.tier
        }
    }


# ── POST /auth/login ──────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password"""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create access token
    token = create_access_token(user.id)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "tier": user.tier
        }
    }


# ── GET /auth/me ──────────────────────────────────────────────────────────────
@router.get("/me")
def get_current_user(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Get current user from token.
    Simple implementation - in production, use proper JWT validation.
    """
    # Extract user_id from token (format: token_123_xxx)
    try:
        parts = token.split('_')
        if len(parts) < 3 or parts[0] != 'token':
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = int(parts[1])
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "tier": user.tier
        }
    except (ValueError, IndexError):
        raise HTTPException(status_code=401, detail="Invalid token format")