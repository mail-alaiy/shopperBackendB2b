from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, Path
import os
from dotenv import load_dotenv
import requests
import json
from bson import ObjectId, json_util
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/orders")
@router.get("/health-check")
def read_root():
    return {"message": "Orders Service is running"}