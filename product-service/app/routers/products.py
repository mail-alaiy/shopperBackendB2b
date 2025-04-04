from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
import os
from dotenv import load_dotenv
from app.database import db
import requests
import json
from bson import ObjectId, json_util

load_dotenv()
ALGOLIA_APP_ID = os.getenv("ALGOLIA_ID")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_ADMIN_KEY")
INDEX_NAME = "product_index"

router = APIRouter()

@router.get("/products")
def get_products(query: str = Query(""),limit: int = Query(10), page: int = Query(1)):
    url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{INDEX_NAME}/query"
    headers = {
        "X-Algolia-API-Key": ALGOLIA_API_KEY,
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "Content-Type": "application/json"
    }
    
    payload = {
        "params": f"query={query}&hitsPerPage={limit}&page={page}"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    
    hits = data.get('hits', [])
    
    return {"message": "Products retreived succesfully", "payload": hits}

@router.get("/product/{product_id}")
def get_product(product_id: str):
    try:
        print(product_id)
        if not ObjectId.is_valid(product_id):
            raise HTTPException(status_code=400, detail="Invalid product ID")

        collection = db["products"]
        object_id = ObjectId(product_id)
        
        document = collection.find_one({"_id": object_id})

        if not document:
            raise HTTPException(status_code=404, detail="Product not found")

        # Safely serialize with json_util
        serialized_doc = json.loads(json_util.dumps(document))

        return {
            "message": "Successfully retrieved the product",
            "payload": serialized_doc
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    