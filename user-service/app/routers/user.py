from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app import models, schemas, auth
from app.database import SessionLocal
from jose import JWTError
from typing import List

router = APIRouter()

# Dependency: Get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Reusable dependency: Get user from x-user-id header
def get_user_by_header(x_user_id: str = Header(..., alias="x-user-id"), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == x_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Signup route
@router.post("/signup", response_model=schemas.UserOut)
def signup(data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

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
        password_hash=auth.hash_password(data.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# Login route
@router.post("/login")
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=data.email).first()
    if not user or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

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
        "user": user,
        "token_type": "bearer"
    }

# Refresh token route
@router.post("/refresh")
def refresh_token(refresh_token: str = Header(...), db: Session = Depends(get_db)):
    try:
        payload = auth.decode_refresh_token(refresh_token)
        user = db.query(models.User).filter(models.User.id == payload["id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

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
    return user

# Update user info
@router.put("/me")
def update_user_info(
    updates: schemas.UserUpdate,
    user: models.User = Depends(get_user_by_header),
    db: Session = Depends(get_db)
):
    update_data = updates.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "password":
            user.password_hash = auth.hash_password(value)
        else:
            setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return {"msg": "User updated successfully"}

# Update password
@router.put("/me/password")
def update_password(
    pw: schemas.PasswordUpdate,
    user: models.User = Depends(get_user_by_header),
    db: Session = Depends(get_db)
):
    if not auth.verify_password(pw.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = auth.hash_password(pw.new_password)
    db.commit()
    return {"msg": "Password updated successfully"}

# Get all users
@router.get("/all", response_model=List[schemas.UserOut])
def get_all_users(db: Session = Depends(get_db), user: models.User = Depends(get_user_by_header)):
    users = db.query(models.User).all()
    return users
