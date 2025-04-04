from pymongo import MongoClient
import certifi
import os
from dotenv import load_dotenv
load_dotenv()
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
host_address = os.getenv("DB_HOST")
database = os.getenv("DB_NAME")
mongo_url = f"mongodb+srv://{username}:{password}@{host_address}/{database}"

mongo_client = MongoClient(mongo_url, tlsCAFile=certifi.where())

db = mongo_client[database]