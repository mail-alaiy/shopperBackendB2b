import argparse
from app.database import SessionLocal, engine, Base
from app.models import User, RoleEnum, BusinessTypeEnum  # Import necessary models and enums
from app.auth import hash_password
import os
from dotenv import load_dotenv

# Load environment variables (especially DB connection)
load_dotenv()

# Optional: Create tables if they don't exist (useful for initial setup)
# Base.metadata.create_all(bind=engine)

def create_admin_user(email: str, password: str, full_name: str, phone_number: str):
    """Creates an admin user in the database."""
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"User with email {email} already exists.")
            return

        # Create the admin user
        # Provide dummy/default values for business info as they are required by the model
        # You might want to adjust these or make them arguments as well
        admin_user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            phone_number=phone_number,
            role=RoleEnum.admin,
            # Fill required business fields with placeholder data for admin
            company_name="Admin Company",
            business_type=BusinessTypeEnum.manufacturer, # Or any default/placeholder
            business_street="N/A",
            business_city="N/A",
            business_state="N/A",
            business_country="N/A",
            gst_number="N/A"
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"Admin user {email} created successfully with ID: {admin_user.id}")

    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", required=True, help="Admin user's email")
    parser.add_argument("--password", required=True, help="Admin user's password")
    parser.add_argument("--name", required=True, help="Admin user's full name")
    parser.add_argument("--phone", required=True, help="Admin user's phone number")

    args = parser.parse_args()

    create_admin_user(
        email=args.email,
        password=args.password,
        full_name=args.name,
        phone_number=args.phone
    ) 