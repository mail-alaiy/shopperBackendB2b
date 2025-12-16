# app/core/database.py

from mongoengine import connect
import os
import certifi
from dotenv import load_dotenv

load_dotenv()
def init_db():
    connect(
        db=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST"),
        alias="default",
        tlsCAFile=certifi.where()
    )
