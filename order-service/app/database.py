from mongoengine import connect
import os
import certifi
from dotenv import load_dotenv

load_dotenv()

db_uri = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")
connect(
    db=db_name,
    host=db_uri,
    tlsCAFile=certifi.where()
)