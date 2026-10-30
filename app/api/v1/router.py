"""Central v1 router: aggregates all endpoint routers under one APIRouter.

Note: the Rafiki webhook receiver and the /rates provider are mounted at the app
root (see app.api.callbacks), not here, because Rafiki calls them without the
/api/v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, payments, users, wallets

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
