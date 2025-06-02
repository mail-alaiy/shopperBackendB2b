from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, Path
import os
from dotenv import load_dotenv
from app.database import db
import requests
import json
from bson import ObjectId, json_util
from pydantic import BaseModel
from typing import List

load_dotenv()
ALGOLIA_APP_ID = os.getenv("ALGOLIA_ID")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_ADMIN_KEY")
INDEX_NAME = "product_index"

router = APIRouter(prefix="/products")

@router.get("")
def get_products(
        query: str = Query(""),
        limit: int = Query(10),
         page: int = Query(1, ge=0),
         min_price: int = Query(None, ge=0),
         max_price: int = Query(None, ge=0)
    ):

    url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{INDEX_NAME}/query"
    headers = {
        "X-Algolia-API-Key": ALGOLIA_API_KEY,
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "Content-Type": "application/json"
    }

    filters = []
    if min_price is not None:
        filters.append(f"price >= {min_price}")
    if max_price is not None:
        filters.append(f"price <= {max_price}")

    filters_str = " AND ".join(filters) if filters else ""

    query_params = [
        f"hitsPerPage={limit}",
        f"page={page}"
    ]
    if query:
        query_params.append(f"query={query}")
    if filters_str:
        query_params.append(f"filters={filters_str}")

    params_str = "&".join(query_params)
    payload = {"params": params_str}
    
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    
    hits = data.get('hits', [])
    
    return {"message": "Products retrieved successfully", "payload": hits}




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
        serialized_doc = json.loads(json_util.dumps(document))

        return {
            "message": "Successfully retrieved the product",
            "payload": serialized_doc
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommend/{product_id}")
def recommend_products(product_id: str = Path(...), max_recommendations: int = Query(10)):
    try:
        if not ObjectId.is_valid(product_id):
            raise HTTPException(status_code=400, detail="Invalid product ID")
        collection = db["products"]
        object_id = ObjectId(product_id)
        document = collection.find_one({"_id": object_id})

        if not document:
            raise HTTPException(status_code=404, detail="Product not found")
        algolia_object_id = str(document["_id"])

        url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/recommendations"
        headers = {
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "Content-Type": "application/json"
        }

        payload = {
            "requests": [
                {
                    "indexName": INDEX_NAME,
                    "objectID": product_id,
                    "model": "related-products",
                    "maxRecommendations": max_recommendations,
                    "threshold": 42.1
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        data = response.json()

        if "results" not in data or not data["results"]:
            return {"message": "No related products found", "payload": []}

        recommendations = data["results"][0].get("hits", [])

        return {
            "message": "Related products retrieved successfully",
            "payload": recommendations
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
class ProductIdsRequest(BaseModel):
    product_ids: List[str]
    
@router.post("/multiple-products")
def get_multiple_products(request: ProductIdsRequest):
    try:
        valid_ids = [ObjectId(pid) for pid in request.product_ids if ObjectId.is_valid(pid)]

        if not valid_ids:
            raise HTTPException(status_code=400, detail="No valid product IDs provided")

        collection = db["products"]
        documents = collection.find({"_id": {"$in": valid_ids}})
        docs_list = list(documents)

        if not docs_list:
            raise HTTPException(status_code=404, detail="No products found")

        serialized_docs = json.loads(json_util.dumps(docs_list))

        return {
            "message": "Successfully retrieved products",
            "payload": serialized_docs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


