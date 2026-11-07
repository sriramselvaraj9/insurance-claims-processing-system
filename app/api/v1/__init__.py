"""API v1 router combining all domain endpoints."""

from fastapi import APIRouter

from app.api.v1.adjusters import router as adjusters_router
from app.api.v1.assessments import router as assessments_router
from app.api.v1.audit import router as audit_router
from app.api.v1.claims import router as claims_router
from app.api.v1.customers import router as customers_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.policies import router as policies_router
from app.api.v1.reserves import router as reserves_router
from app.api.v1.settlements import router as settlements_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(customers_router)
api_router.include_router(policies_router)
api_router.include_router(claims_router)
api_router.include_router(documents_router)
api_router.include_router(adjusters_router)
api_router.include_router(assessments_router)
api_router.include_router(reserves_router)
api_router.include_router(settlements_router)
api_router.include_router(audit_router)
