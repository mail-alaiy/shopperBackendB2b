from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, Path, Response
import os
from dotenv import load_dotenv
from app.database import db, demo_db
import requests
import json
from bson import ObjectId, json_util
from pydantic import BaseModel
from typing import List
import csv
import io

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


@router.get("/amazon/categories")
def get_unique_amazon_categories():
    try:
        collection = demo_db["products_trial_categories"]

        categories = collection.distinct("amazon_cat")

        return {
            "message": "Unique Amazon categories retrieved successfully",
            "payload": categories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/amazon/products-by-category")
def get_amazon_products_by_category(
        category: str = Query(...),
        skip: int = 0,
        limit: int = 20
):
    try:
        collection = demo_db["products_trial_categories"]
        total_count = collection.count_documents({"amazon_cat": category})

        products_cursor = collection.find(
            {
                "amazon_cat": category
            }
        ).skip(skip).limit(limit)

        products = json.loads(json_util.dumps(list(products_cursor)))

        return {
            "message": f"Amazon products retrieved successfully for category: {category}",
            "payload": products,
            "total_count": total_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/fulfillmen-matches")
def get_fulfillmen_matches_by_asin(asin: str = Query(...)):
    try:
        collection = demo_db["products_trial_categories"]

        amazon_product = collection.find_one({
            "amazon_asin": asin,
        })

        if not amazon_product:
            raise HTTPException(status_code=404, detail="Amazon product not found")

        parent_product = amazon_product.get("parent_product")

        if not parent_product:
            raise HTTPException(status_code=404, detail="Parent product not found for this ASIN")

        fulfillmen_cursor = collection.find({
            "parent_product": parent_product,
            "is_amazon_product": {"$ne": "1"}
        })

        fulfillmen_products = json.loads(json_util.dumps(list(fulfillmen_cursor)))

        return {
            "message": f"Fulfillmen matches retrieved successfully for ASIN: {asin}",
            "payload": fulfillmen_products
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/fulfillmen-product-details")
def get_fulfillmen_product_details(_id: str = Query(...)):
    try:
        collection = demo_db["products_trial_categories"]

        object_id = ObjectId(_id)

        product = collection.find_one({
            "_id": object_id,
        })

        if not product:
            raise HTTPException(status_code=404, detail="Fulfillmen product not found")

        product_json = json.loads(json_util.dumps(product))

        return {
            "message": "Fulfillmen product details retrieved successfully",
            "payload": product_json
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/fulfillmen/matches/download-csv")
def download_fulfillmen_matches_csv(asin: str = Query(...)):

    try:
        collection = demo_db["products_trial_categories"]

        products_cursor = collection.find({"amazon_asin": asin})
        products = list(products_cursor)

        if not products:
            raise HTTPException(status_code=404, detail="No products found for this ASIN")

        # Prepare CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Defining CSV header with fields
        header = [
            "ASIN",
            "Title",
            "Amazon Product Price",
            "Amazon Product URL",
            "Amazon Product Image URL",
            "SKU",
            "Parent Product",
            "is_amazon_product",
        ]
        writer.writerow(header)

        # Write product rows
        for product in products:
            skus = product.get("skus", "")
            if isinstance(skus, list):
                skus = ",".join([str(sku) for sku in skus])
            row = [
                product.get("amazon_asin", ""),
                product.get("name", ""),
                product.get("amazon_product_price", ""),
                product.get("amazon_product_url", ""),
                product.get("amazon_product_image_url", ""),
                skus,
                product.get("parent_product", ""),
                product.get("is_amazon_product", ""),
            ]
            writer.writerow(row)

        output.seek(0)
        csv_content = output.getvalue()

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=fulfillmen_matches_{asin}.csv"
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/amazon/product-details")
def get_amazon_product_details(asin: str = Query(...)):
    try:
        collection = demo_db["products_trial_categories"]

        product = collection.find_one({"amazon_asin": asin})

        if not product:
            raise HTTPException(status_code=404, detail="Amazon product not found")

        product["_id"] = str(product["_id"])

        return {"message": "Amazon product details retrieved successfully", "payload": product}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/amazon/{product_id}")
def get_product_by_id(product_id: str):
    try:
        collection = demo_db["products_trial_categories"]

        # Validate ObjectId
        if not ObjectId.is_valid(product_id):
            raise HTTPException(status_code=400, detail="Invalid product ID")

        product = collection.find_one({"_id": ObjectId(product_id)})

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        product_json = json.loads(json_util.dumps(product))

        return {
            "message": "Product retrieved successfully",
            "payload": product_json
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))