from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, Path
import os
from dotenv import load_dotenv
from database import db
import requests
import json
from bson import ObjectId, json_util
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/products")
@router.get("/health-check")
def read_root():
    return {"message": "Product Service is running"}