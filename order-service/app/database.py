from mongoengine import connect
import os
from dotenv import load_dotenv

load_dotenv()

# Use this from .env
db_uri = os.getenv("DB_HOST")         # Full URI for Atlas
db_name = os.getenv("DB_NAME")

# Connect to Atlas using full URI
connect(
    db=db_name,
    host=db_uri
)
