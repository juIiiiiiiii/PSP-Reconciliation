"""
Ledger Entry Model (Double-Entry Accounting)
"""

from datetime import datetime, date
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class LedgerEntry(BaseModel):
    """Double-entry ledger entry"""
    
    ledger_entry_id: UUID
    tenant_id: UUID
    entity_id: UUID
    transaction_date: date
    account_debit: str = Field(..., description="Chart of accounts code")
    account_credit: str = Field(..., description="Chart of accounts code")
    amount: int = Field(..., description="Amount in cents")
    currency: str = Field(..., max_length=3)
    reference_transaction_id: Optional[UUID] = None
    reference_match_id: Optional[UUID] = None
    reference_adjustment_id: Optional[UUID] = None
    description: str
    posted_at: datetime
    posted_by_system: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }


