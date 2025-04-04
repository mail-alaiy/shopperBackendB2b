import bcrypt
from jose import jwt
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, UTC

load_dotenv()
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
REFRESH_TOKEN_SECRET = os.getenv("REFRESH_TOKEN_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")

def hash_password(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw, hash): return bcrypt.checkpw(pw.encode(), hash.encode())

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, ACCESS_TOKEN_SECRET, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, REFRESH_TOKEN_SECRET, algorithm=ALGORITHM)

def decode_access_token(token): 
    return jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=[ALGORITHM])

def decode_refresh_token(token): 
    return jwt.decode(token, REFRESH_TOKEN_SECRET, algorithms=[ALGORITHM])
