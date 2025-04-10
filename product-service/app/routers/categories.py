from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
import os
from dotenv import load_dotenv
from app.database import db
from bson import json_util
import json
from bson import ObjectId
import requests

load_dotenv()
ALGOLIA_APP_ID = os.getenv("ALGOLIA_ID")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_ADMIN_KEY")
INDEX_NAME = "product_index"

router = APIRouter()
    
@router.get("/categories")
def get_categories():
    categories_collection = db["amazonCategories"]
    try:
        documents = categories_collection.find()
        if not documents:
            raise HTTPException(status_code=404, detail="Categories are not being retreived")
        
        serialized_docs = json.loads(json_util.dumps(documents))
        return {
            "message": "Successfully retrieved all categories",
            "payload": serialized_docs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/category/{category_id}")
def get_products(category_id: str, limit: int = Query(10), page: int = Query(1)):
    try:
        # Step 1: Get category name from MongoDB
        collection = db["amazonCategories"]
        object_id = ObjectId(category_id)
        doc = collection.find_one({"_id": object_id})

        if not doc or "category" not in doc:
            return {"message": "Category not found", "payload": []}

        category_query = doc["category"]

        # Step 2: Algolia API request
        url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{INDEX_NAME}/query"
        headers = {
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "Content-Type": "application/json"
        }
        payload = {
            "params": f"query={category_query}&hitsPerPage={limit}&page={page}&optionalWords={category_query}"
        }

        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        hits = data.get('hits', [])

        return {"message": "Products retrieved successfully", "payload": hits}

    except Exception as e:
        print(f"Error: {e}")
        return {"message": "Something went wrong", "error": str(e), "payload": []}