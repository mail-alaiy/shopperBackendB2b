from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
import os
from dotenv import load_dotenv

load_dotenv()
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")

def decode_access_token(token): 
    return jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=[ALGORITHM])

def get_current_user(authorization: str = Header(...)):
    try:
        # Split the Authorization header into "Bearer" and the actual token
        scheme, token = authorization.split()

        # Make sure the scheme is "Bearer"
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        # Decode the JWT token
        payload = decode_access_token(token)

        # Query the user by ID
        return payload["id"]
    
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError:
        # This happens if authorization header format is wrong
        raise HTTPException(status_code=401, detail="Invalid authorization header format")