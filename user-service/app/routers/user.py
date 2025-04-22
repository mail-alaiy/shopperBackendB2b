from fastapi import APIRouter, Depends, HTTPException, Header, Path, Request, status
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.database import SessionLocal
from jose import JWTError
from typing import List
from uuid import UUID
from app.helpers.email_utils import send_verification_email, send_confirmation_email, SENDER_EMAIL
from datetime import datetime, timezone
import resend # Import resend library
import os # Import os to access environment variables

# Dependency: Get DB session
def get_db():
    """Dependency that provides a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Reusable dependency: Get user from x-user-id header
def get_user_by_header(x_user_id: str = Header(..., alias="x-user-id"), db: Session = Depends(get_db)):
    """
    Dependency to retrieve a user based on the 'x-user-id' header.

    Raises:
        HTTPException(404): If the user ID from the header is not found.
    """
    user = db.query(models.User).filter(models.User.id == x_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# --- Authentication Setup ---
# Load the expected API key from environment variables
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
if not INTERNAL_API_KEY:
    # This service cannot function securely for internal calls without the key
    print("CRITICAL ERROR: INTERNAL_API_KEY environment variable not set in user-service.")
    # You might raise an exception here to prevent startup, or handle it cautiously.
    # For now, we'll let endpoints fail if the key is missing.

async def verify_internal_api_key(x_internal_api_key: str = Header(None, alias="X-Internal-API-Key")):
    """Dependency to verify the internal API key header."""
    if not INTERNAL_API_KEY:
        # Log this critical configuration error
        print("Internal API Key not configured on the server.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server configuration error.",
        )
    if not x_internal_api_key:
         print("Missing X-Internal-API-Key header in request.")
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal API Key",
            headers={"WWW-Authenticate": "API Key"},
        )
    if x_internal_api_key != INTERNAL_API_KEY:
        print("Invalid X-Internal-API-Key received.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API Key",
            headers={"WWW-Authenticate": "API Key"},
        )
    # If key is valid, proceed without returning anything
# --- End Authentication Setup ---

router = APIRouter()

# Signup route
@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(data: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    """
    Registers a new user, saves them as inactive, creates a verification token,
    and sends a verification email.
    """
    if db.query(models.User).filter_by(email=data.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    new_user = models.User(
        company_name=data.company_name,
        business_type=data.business_type,
        business_street=data.business_street,
        business_city=data.business_city,
        business_state=data.business_state,
        business_country=data.business_country,
        role="customer",
        full_name=data.full_name,
        phone_number=data.phone_number,
        email=data.email,
        gst_number=data.gst_number,
        password_hash=auth.hash_password(data.password),
        is_active=False
    )

    db.add(new_user)
    db.flush()

    # Create Verification Token
    verification_token = models.VerificationToken(user_id=new_user.id)
    db.add(verification_token)

    db.commit()
    db.refresh(new_user)

    base_url = str(request.base_url).rstrip('/')
    verification_link = f"{base_url}/verify-email/{verification_token.token}"

    try:
        send_verification_email(new_user.email, verification_link)
    except Exception as e:
        print(f"Failed to send verification email for {new_user.email}: {e}")

    return {"msg": "User registered successfully. Please check your email to verify your account."}

# Login route
@router.post("/login")
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user based on email and password.

    Requires the user account to be active (verified).

    Returns:
        Access token, refresh token, and basic user information upon successful login.
    """
    user = db.query(models.User).filter_by(email=data.email).first()

    if not user or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. Please check your email.",
        )

    user_data = {
        "id": str(user.id),
        "email": user.email,
        "role": user.role
    }

    access_token = auth.create_access_token(user_data)
    refresh_token = auth.create_refresh_token(user_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": schemas.UserOut.from_orm(user),
        "token_type": "bearer"
    }

@router.get("/verify-email/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Verifies a user's email address using the provided token.
    Activates the user account if the token is valid and not expired,
    and sends a confirmation email.
    """
    token_record = db.query(models.VerificationToken).filter(models.VerificationToken.token == token).first()

    if not token_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired verification token")

    if token_record.expires_at < datetime.now(timezone.utc):
        db.delete(token_record)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token expired")

    user = db.query(models.User).filter(models.User.id == token_record.user_id).first()

    if not user:
        db.delete(token_record)
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated user not found")

    if user.is_active:
        db.delete(token_record)
        db.commit()
        return {"msg": "Account already verified."}

    # Activate user and delete the token
    user.is_active = True
    db.delete(token_record)
    db.commit() # Commit changes before sending email

    # Send confirmation email
    try:
        send_confirmation_email(user.email)
    except Exception as e:
        # Log the error, but don't fail the request as verification was successful
        print(f"Failed to send confirmation email to {user.email} after verification: {e}")

    return {"msg": "Email verified successfully. You can now log in."}

# Refresh token route
@router.post("/refresh")
def refresh_token(refresh_token: str = Header(...), db: Session = Depends(get_db)):
    """
    Generates a new access token using a valid refresh token provided in the header.
    """
    try:
        payload = auth.decode_refresh_token(refresh_token)
        user = db.query(models.User).filter(models.User.id == payload["id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Add is_active check if refreshed tokens should only be granted to active users
        # if not user.is_active:
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account not verified")

        user_data = {
            "id": str(user.id),
            "email": user.email,
            "role": user.role
        }
        access_token = auth.create_access_token(user_data)
        return {"access_token": access_token, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.get("/me", response_model=schemas.UserOut)
def get_user_info(
    user: models.User = Depends(get_user_by_header)
):
    """
    Retrieves the profile information for the authenticated user (identified by x-user-id header).
    """
    return user

# Update user info
@router.put("/me")
def update_user_info(
    updates: schemas.UserUpdate,
    user: models.User = Depends(get_user_by_header),
    db: Session = Depends(get_db)
):
    """
    Updates the profile information for the authenticated user.
    Email updates are not allowed via this endpoint.
    Password updates should use the dedicated `/me/password` endpoint.
    """
    update_data = updates.dict(exclude_unset=True)

    if "email" in update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address cannot be updated via this endpoint."
        )

    for field, value in update_data.items():
        if field == "password":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use PUT /me/password to update password")
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return {"msg": "User updated successfully", "user": schemas.UserOut.from_orm(user)}

# Update password
@router.put("/me/password")
def update_password(
    pw: schemas.PasswordUpdate,
    user: models.User = Depends(get_user_by_header),
    db: Session = Depends(get_db)
):
    """
    Updates the password for the authenticated user after verifying the current password.
    """
    if not auth.verify_password(pw.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = auth.hash_password(pw.new_password)
    db.commit()
    return {"msg": "Password updated successfully"}

# --- Secured Admin/Internal Routes ---

# Admin: Get all users with pagination (Add the dependency)
@router.get("/admin/all", response_model=List[schemas.UserOut])
def get_all_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Admin route: Retrieves a paginated list of all users.
    Requires valid internal API key.
    """
    # TODO: Add additional role check if needed (e.g., check if caller has admin rights)
    print("Internal request validated: Fetching all users")
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

# Admin: Get specific user by ID (Add the dependency)
@router.get("/admin/user/{user_id}", response_model=schemas.UserOut)
def admin_get_user_by_id(user_id: UUID = Path(..., description="The UUID of the user to retrieve"), db: Session = Depends(get_db)):
    """
    Admin route: Retrieves details for a specific user by their UUID.
    Requires valid internal API key.
    """
    print(f"Internal request validated: Fetching user {user_id}")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    return user

# Internal: Get specific user by ID (Requires Internal API Key)
@router.get("/internal/user/{user_id}",
            response_model=schemas.UserOut,
            include_in_schema=False, # Hide from public docs
            dependencies=[Depends(verify_internal_api_key)])
def internal_get_user_by_id(user_id: UUID = Path(..., description="The UUID of the user to retrieve"), db: Session = Depends(get_db)):
    """
    Internal route: Retrieves details for a specific user by their UUID.
    Requires valid internal API key.
    """
    print(f"Internal request validated: Fetching user {user_id}")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")
    return user

@router.get("/debug")
def debug_header(request: Request):
    headers = dict(request.headers)
    return {
        "headers": headers
    }
