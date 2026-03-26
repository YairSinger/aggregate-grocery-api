from fastapi import APIRouter
from app.api.v1.endpoints import optimization, aggregates, shopping_lists, items, auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(optimization.router, prefix="/optimize", tags=["optimization"])
api_router.include_router(aggregates.router, prefix="/aggregates", tags=["aggregates"])
api_router.include_router(shopping_lists.router, prefix="/shopping-lists", tags=["shopping-lists"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
