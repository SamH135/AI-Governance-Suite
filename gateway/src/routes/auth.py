"""Authentication routes for the gateway service."""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
import jwt
from jwt import PyJWTError as JWTError
import asyncpg
import redis.asyncio as redis

# Import custom logger
from ..logger_util import logger

from ..shared.database import get_db_pool
from ..shared.cache import get_redis_client
from ..shared.config import get_settings
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models
class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None

class TokenRefresh(BaseModel):
    refresh_token: str

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

class UserResponse(BaseModel):
    user_id: int
    username: str
    full_name: str
    email: Optional[str]
    role: str
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool

class LoginResponse(BaseModel):
    success: bool
    data: dict
    message: Optional[str] = None

# Helper functions
def truncate_password_for_bcrypt(password: str) -> str:
    """Truncate password to 72 bytes max for bcrypt compatibility"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # Truncate to 72 bytes (not chars) to handle multi-byte characters
        truncated = password_bytes[:72].decode('utf-8', errors='ignore')
        return truncated
    return password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    # Truncate password before verification to match registration behavior
    password_to_verify = truncate_password_for_bcrypt(plain_password)
    result = pwd_context.verify(password_to_verify, hashed_password)
    return result

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    # Truncate password before hashing to ensure bcrypt compatibility
    password_to_hash = truncate_password_for_bcrypt(password)
    hash_result = pwd_context.hash(password_to_hash)
    return hash_result

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    logger.debug("Creating access token", function="create_access_token", user_id=data.get("user_id"), username=data.get("sub"))
    
    settings = get_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        logger.debug("Using custom expiration delta", function="create_access_token", expires_delta=str(expires_delta))
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
        logger.debug("Using default expiration", function="create_access_token", hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    logger.debug("Access token created successfully", function="create_access_token", expires_at=expire.isoformat())
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    logger.debug("Authenticating user from JWT token", function="get_current_user")
    
    settings = get_settings()
    token = credentials.credentials
    
    try:
        logger.debug("Decoding JWT token", function="get_current_user")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("user_id")
        username: str = payload.get("sub")
        
        logger.debug("JWT token decoded", function="get_current_user", user_id=user_id, username=username)
        
        if user_id is None or username is None:
            logger.warn("Invalid JWT payload - missing user_id or username", function="get_current_user")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError as e:
        logger.warn("JWT decoding failed", function="get_current_user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    logger.debug("Fetching user from database", function="get_current_user", user_id=user_id)
    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, username, full_name, email, role, created_at, last_login, is_active "
            "FROM users WHERE user_id = $1 AND is_active = TRUE",
            user_id
        )
    
    if user is None:
        logger.warn("User not found or inactive", function="get_current_user", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    logger.debug("User authenticated successfully", function="get_current_user", user_id=user_id, username=user["username"])
    return dict(user)

@router.post("/login", response_model=LoginResponse)
async def login(user_data: UserLogin):
    """User login endpoint"""
    logger.info("User login attempt", function="login", username=user_data.username)
    
    settings = get_settings()
    
    try:
        # Get user from database
        logger.debug("Fetching user from database", function="login", username=user_data.username)
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id, username, password_hash, full_name, email, role, is_active "
                "FROM users WHERE username = $1",
                user_data.username
            )
        
        if not user:
            logger.warn("Login failed - user not found", function="login", username=user_data.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_CREDENTIALS", "message": "Invalid username or password"}
            )
        
        if not user["is_active"]:
            logger.warn("Login failed - account disabled", function="login", username=user_data.username, user_id=user["user_id"])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "ACCOUNT_DISABLED", "message": "Account is disabled"}
            )
        
        # Verify password
        logger.debug("Verifying user password", function="login", username=user_data.username, user_id=user["user_id"])
        if not verify_password(user_data.password, user["password_hash"]):
            logger.warn("Login failed - invalid password", function="login", username=user_data.username, user_id=user["user_id"])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_CREDENTIALS", "message": "Invalid username or password"}
            )
        
        # Create tokens
        logger.debug("Creating access and refresh tokens", function="login", user_id=user["user_id"], username=user["username"])
        token_data = {
            "sub": user["username"],
            "user_id": user["user_id"],
            "role": user["role"]
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_access_token(
            token_data, 
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        # Store refresh token in Redis
        logger.debug("Storing refresh token in Redis", function="login", user_id=user["user_id"])
        redis_client = get_redis_client()
        await redis_client.set(
            f"refresh_token:{user['user_id']}", 
            refresh_token, 
            ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        )
        logger.debug("Refresh token stored successfully", function="login", user_id=user["user_id"])
        
        # Update last login
        logger.debug("Updating last login timestamp", function="login", user_id=user["user_id"])
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = $1",
                user["user_id"]
            )
        logger.debug("Last login timestamp updated", function="login", user_id=user["user_id"])
        
        # Prepare response
        user_response = {k: v for k, v in user.items() if k != "password_hash"}
        
        logger.info("User logged in successfully", function="login", user_id=user["user_id"], username=user["username"], role=user["role"])
        
        return LoginResponse(
            success=True,
            data={
                "user": user_response,
                "token": access_token,
                "refresh_token": refresh_token,
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error occurred", function="login", username=user_data.username, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "LOGIN_ERROR", "message": "Login failed"}
        )

@router.post("/register", response_model=LoginResponse)
async def register(user_data: UserRegister):
    """User registration endpoint"""
    logger.info("User registration attempt", function="register", username=user_data.username, email=user_data.email)
    
    try:
        db_pool = get_db_pool()
        
        # Check if username exists
        logger.debug("Checking if username already exists", function="register", username=user_data.username)
        async with db_pool.acquire() as conn:
            existing_user = await conn.fetchval(
                "SELECT user_id FROM users WHERE username = $1", 
                user_data.username
            )
        
        if existing_user:
            logger.warn("Registration failed - username already exists", function="register", username=user_data.username)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "USERNAME_EXISTS", "message": "Username already exists"}
            )
        
        # Check if email exists (if provided)
        if user_data.email:
            logger.debug("Checking if email already exists", function="register", email=user_data.email)
            async with db_pool.acquire() as conn:
                existing_email = await conn.fetchval(
                    "SELECT user_id FROM users WHERE email = $1", 
                    user_data.email
                )
            
            if existing_email:
                logger.warn("Registration failed - email already exists", function="register", email=user_data.email)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "EMAIL_EXISTS", "message": "Email already exists"}
                )
        
        # Create user
        logger.debug("Creating new user account", function="register", username=user_data.username)
        password_hash = get_password_hash(user_data.password)
        
        async with db_pool.acquire() as conn:
            new_user = await conn.fetchrow(
                """INSERT INTO users (username, password_hash, full_name, email) 
                   VALUES ($1, $2, $3, $4) 
                   RETURNING user_id, username, full_name, email, role, created_at, is_active""",
                user_data.username, password_hash, user_data.full_name, user_data.email
            )
        logger.debug("User account created successfully", function="register", user_id=new_user["user_id"])
        
        # Log in the new user
        logger.debug("Logging in new user", function="register", user_id=new_user["user_id"])
        
        settings = get_settings()
        
        # Create tokens
        logger.debug("Creating access and refresh tokens", function="login", user_id=new_user["user_id"], username=new_user["username"])
        token_data = {
            "sub": new_user["username"],
            "user_id": new_user["user_id"],
            "role": new_user["role"]
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_access_token(
            token_data, 
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        # Store refresh token in Redis
        logger.debug("Storing refresh token in Redis", function="login", user_id=new_user["user_id"])
        redis_client = get_redis_client()
        await redis_client.set(
            f"refresh_token:{new_user['user_id']}", 
            refresh_token, 
            ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        )
        logger.debug("Refresh token stored successfully", function="login", user_id=new_user["user_id"])
        
        # Update last login
        logger.debug("Updating last login timestamp", function="login", user_id=new_user["user_id"])
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = $1",
                new_user["user_id"]
            )
        logger.debug("Last login timestamp updated", function="login", user_id=new_user["user_id"])
        
        # Prepare response
        user_response = {k: v for k, v in new_user.items() if k != "password_hash"}
        
        logger.info("User registered and logged in successfully", function="register", user_id=new_user["user_id"], username=new_user["username"], role=new_user["role"])
        
        return LoginResponse(
            success=True,
            data={
                "user": user_response,
                "token": access_token,
                "refresh_token": refresh_token,
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration error occurred", function="register", username=user_data.username, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "REGISTRATION_ERROR", "message": "Registration failed"}
        )

@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(token_data: TokenRefresh):
    """Refresh access token"""
    logger.info("Token refresh attempt", function="refresh_token")
    
    settings = get_settings()
    
    try:
        # Verify refresh token
        logger.debug("Verifying refresh token", function="refresh_token")
        payload = jwt.decode(token_data.refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id")
        
        logger.debug("Refresh token decoded", function="refresh_token", user_id=user_id)
        
        if user_id is None:
            logger.warn("Invalid refresh token - missing user_id", function="refresh_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"}
            )
        
        # Check if refresh token exists in Redis
        logger.debug("Checking refresh token in Redis", function="refresh_token", user_id=user_id)
        redis_client = get_redis_client()
        stored_token = await redis_client.get(f"refresh_token:{user_id}")
        if not stored_token or stored_token.decode() != token_data.refresh_token:
            logger.warn("Invalid or expired refresh token", function="refresh_token", user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid or expired refresh token"}
            )
        
        # Get user from database
        logger.debug("Fetching user from database for token refresh", function="refresh_token", user_id=user_id)
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id, username, full_name, email, role, is_active "
                "FROM users WHERE user_id = $1",
                user_id
            )
        
        if not user or not user["is_active"]:
            logger.warn("User not found or inactive during token refresh", function="refresh_token", user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "USER_NOT_FOUND", "message": "User not found or inactive"}
            )
        
        # Generate new access token
        logger.debug("Generating new access token", function="refresh_token", user_id=user["user_id"], username=user["username"])
        token_payload = {
            "sub": user["username"],
            "user_id": user["user_id"],
            "role": user["role"]
        }
        
        new_access_token = create_access_token(token_payload)
        
        logger.info("Token refreshed successfully", function="refresh_token", user_id=user["user_id"], username=user["username"])
        
        return LoginResponse(
            success=True,
            data={
                "user": dict(user),
                "token": new_access_token,
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600
            }
        )
        
    except JWTError as e:
        logger.warn("JWT error during token refresh", function="refresh_token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh error occurred", function="refresh_token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "REFRESH_ERROR", "message": "Token refresh failed"}
        )

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """User logout endpoint"""
    logger.info("User logout attempt", function="logout", user_id=current_user["user_id"], username=current_user["username"])
    
    try:
        # Remove refresh token from Redis
        logger.debug("Removing refresh token from Redis", function="logout", user_id=current_user["user_id"])
        redis_client = get_redis_client()
        await redis_client.delete(f"refresh_token:{current_user['user_id']}")
        
        logger.info("User logged out successfully", function="logout", user_id=current_user["user_id"], username=current_user["username"])
        
        return {"success": True, "message": "Logged out successfully"}
        
    except Exception as e:
        logger.error("Logout error occurred", function="logout", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "LOGOUT_ERROR", "message": "Logout failed"}
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    logger.debug("Fetching current user information", function="get_current_user_info", user_id=current_user["user_id"], username=current_user["username"])
    
    try:
        result = UserResponse(**current_user)
        logger.debug("Current user information retrieved successfully", function="get_current_user_info", user_id=current_user["user_id"])
        return result
    except Exception as e:
        logger.error("Failed to retrieve current user information", function="get_current_user_info", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's profile (full_name, email)"""
    logger.info("Profile update requested", function="update_profile", user_id=current_user["user_id"])

    updates = profile.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    try:
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            if "email" in updates:
                existing = await conn.fetchrow(
                    "SELECT user_id FROM users WHERE email = $1 AND user_id != $2",
                    updates["email"], current_user["user_id"]
                )
                if existing:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

            set_clause = ", ".join(f"{k} = ${i}" for i, k in enumerate(updates, start=2))
            user = await conn.fetchrow(
                f"""UPDATE users SET {set_clause} WHERE user_id = $1
                    RETURNING user_id, username, full_name, email, role, created_at, last_login, is_active""",
                current_user["user_id"], *updates.values()
            )

        logger.info("Profile updated successfully", function="update_profile", user_id=current_user["user_id"])
        return UserResponse(**dict(user))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update profile", function="update_profile", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile")

@router.put("/password")
async def change_password(
    body: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change current user's password after verifying the current one"""
    logger.info("Password change requested", function="change_password", user_id=current_user["user_id"])

    try:
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT password_hash FROM users WHERE user_id = $1",
                current_user["user_id"]
            )
            if not user or not verify_password(body.current_password, user["password_hash"]):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

            await conn.execute(
                "UPDATE users SET password_hash = $2 WHERE user_id = $1",
                current_user["user_id"], get_password_hash(body.new_password)
            )

        # Invalidate existing refresh tokens so new password is required for future sessions
        redis_client = get_redis_client()
        await redis_client.delete(f"refresh_token:{current_user['user_id']}")

        logger.info("Password changed successfully", function="change_password", user_id=current_user["user_id"])
        return {"success": True, "message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to change password", function="change_password", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to change password")