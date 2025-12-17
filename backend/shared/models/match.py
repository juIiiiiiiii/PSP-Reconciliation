"""
Reconciliation Match Model
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class MatchLevel(int, Enum):
    """Matching confidence levels"""
    STRONG_ID = 1  # 100% confidence
    PSP_REFERENCE = 2  # 95% confidence
    FUZZY = 3  # 70-90% confidence
    AMOUNT_DATE = 4  # 50-70% confidence


class MatchMethod(str, Enum):
    """How the match was created"""
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    RULE = "RULE"


class MatchStatus(str, Enum):
    """Match status"""
    MATCHED = "MATCHED"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    PENDING_REVIEW = "PENDING_REVIEW"


class ReconciliationMatch(BaseModel):
    """Reconciliation match between transaction and settlement"""
    
    match_id: UUID
    tenant_id: UUID
    transaction_id: UUID
    settlement_id: Optional[UUID] = None
    match_level: MatchLevel
    confidence_score: Decimal = Field(..., ge=0, le=100, description="0-100")
    match_method: MatchMethod
    amount_difference: Optional[int] = None  # cents (transaction - settlement)
    amount_difference_percent: Optional[Decimal] = None
    matched_by_user_id: Optional[UUID] = None  # NULL for auto-matches
    matched_at: datetime
    status: MatchStatus
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            Decimal: float,
        }


