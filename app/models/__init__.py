"""SQLAlchemy Declarative Models for Insurance Claims Processing System."""

from app.models.adjuster import Adjuster
from app.models.adjuster_assignment import AdjusterAssignment
from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.base import Base, TimestampMixin
from app.models.claim import Claim
from app.models.claim_item import ClaimItem
from app.models.claim_status_history import ClaimStatusHistory
from app.models.coverage import Coverage
from app.models.customer import Customer
from app.models.document import Document
from app.models.document_request import DocumentRequest
from app.models.incident import Incident
from app.models.policy import Policy
from app.models.reserve import Reserve
from app.models.settlement import Settlement
from app.models.settlement_payment import SettlementPayment

__all__ = [
    "Base",
    "TimestampMixin",
    "Customer",
    "Policy",
    "Coverage",
    "Incident",
    "Claim",
    "ClaimItem",
    "Document",
    "DocumentRequest",
    "Adjuster",
    "AdjusterAssignment",
    "Assessment",
    "Reserve",
    "Settlement",
    "SettlementPayment",
    "ClaimStatusHistory",
    "AuditEvent",
]
