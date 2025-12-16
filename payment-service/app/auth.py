from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# Read secrets and algorithm from environment variables
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")

# Ensure required environment variables are set
if not ACCESS_TOKEN_SECRET:
    raise ValueError("ACCESS_TOKEN_SECRET environment variable not set.")
if not ALGORITHM:
    raise ValueError("JWT_ALGORITHM environment variable not set.")

def decode_access_token(token):
    """Decodes the JWT access token."""
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        # Log the specific JWT error for debugging
        print(f"JWT Error: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials - Invalid token")

def get_current_user(authorization: str = Header(...)):
    """Dependency to get the current user ID from the Authorization header."""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Split the Authorization header into "Bearer" and the actual token
        scheme, token = authorization.split()

        # Make sure the scheme is "Bearer"
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        # Decode the JWT token
        payload = decode_access_token(token)

        # Extract user ID from payload
        user_id = payload.get("id")
        if user_id is None:
            # If 'id' is not in the payload, raise an exception
            raise credentials_exception
        
        # Return the user ID
        return user_id
    
    except ValueError:
        # This happens if authorization header format is wrong (e.g., no space)
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    except Exception as e:
        # Catch any other unexpected errors during authentication
        print(f"Authentication Error: {e}")
        raise credentials_exception 