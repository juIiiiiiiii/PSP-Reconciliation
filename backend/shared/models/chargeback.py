"""
Chargeback Model
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class ChargebackStatus(str, Enum):
    """Chargeback lifecycle status"""
    INITIATED = "INITIATED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    DISPUTED = "DISPUTED"
    WON = "WON"
    LOST = "LOST"
    REVERSED = "REVERSED"


class Chargeback(BaseModel):
    """Chargeback and dispute record"""
    
    chargeback_id: UUID
    tenant_id: UUID
    transaction_id: UUID
    psp_chargeback_id: str
    chargeback_reason: Optional[str] = None
    chargeback_reason_code: Optional[str] = None
    chargeback_amount: int = Field(..., description="Amount in cents")
    chargeback_currency: str = Field(..., max_length=3)
    chargeback_date: date
    dispute_deadline: Optional[date] = None
    status: ChargebackStatus = ChargebackStatus.INITIATED
    dispute_evidence: Dict[str, Any] = Field(default_factory=dict)
    assigned_to_user_id: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolved_by_user_id: Optional[UUID] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }


