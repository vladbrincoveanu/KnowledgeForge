"""Sample FastAPI application for testing."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Test API", version="1.0.0")


class Item(BaseModel):
    name: str
    price: float


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hello World"}


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    """Get item by ID."""
    return {"item_id": item_id, "name": f"Item {item_id}"}


@app.post("/items")
async def create_item(item: Item):
    """Create new item."""
    return {"id": 1, "name": item.name, "price": item.price}


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    """Update item."""
    return {"id": item_id, "name": item.name, "price": item.price}


@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    """Delete item."""
    return {"deleted": item_id}
