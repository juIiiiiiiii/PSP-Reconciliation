"""
Reconciliation Exception Model
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ExceptionType(str, Enum):
    """Exception types"""
    UNMATCHED = "UNMATCHED"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE = "DUPLICATE"
    TIMING_MISMATCH = "TIMING_MISMATCH"


class ExceptionPriority(str, Enum):
    """Exception priority levels"""
    P1 = "P1"  # Critical: >$10k, immediate attention
    P2 = "P2"  # High: >$1k, within 4 hours
    P3 = "P3"  # Medium: >$100, within 24 hours
    P4 = "P4"  # Low: <$100, daily review


class ExceptionStatus(str, Enum):
    """Exception status"""
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    EXPECTED = "EXPECTED"  # No settlement expected (e.g., pending auth)


class ReconciliationException(BaseModel):
    """Reconciliation exception (unmatched or problematic transaction)"""
    
    exception_id: UUID
    tenant_id: UUID
    transaction_id: Optional[UUID] = None
    settlement_id: Optional[UUID] = None
    exception_type: ExceptionType
    exception_reason: Optional[str] = None
    amount_value: Optional[int] = None  # cents
    amount_currency: Optional[str] = None
    priority: ExceptionPriority = ExceptionPriority.P3
    status: ExceptionStatus = ExceptionStatus.OPEN
    assigned_to_user_id: Optional[UUID] = None
    resolved_by_user_id: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


