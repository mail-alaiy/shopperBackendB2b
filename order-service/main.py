from fastapi import FastAPI
from app.routers import orders

app = FastAPI()
app.include_router(orders.router)

@app.get("/health-check")
def read_root():
    return {"message": "Cart Service is running"} 