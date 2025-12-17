"""
PSP Settlement Model
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class PSPSettlement(BaseModel):
    """PSP settlement record from settlement files"""
    
    settlement_id: UUID
    tenant_id: UUID
    psp_connection_id: str
    settlement_date: date
    settlement_batch_id: str
    settlement_line_number: int
    amount_value: int = Field(..., description="Amount in cents")
    amount_currency: str = Field(..., max_length=3)
    psp_settlement_id: Optional[str] = None
    psp_transaction_ids: List[str] = Field(default_factory=list)
    psp_fee: Optional[int] = None  # cents
    net_amount: Optional[int] = None  # cents
    source_file_path: Optional[str] = None
    source_parser_version: Optional[str] = None
    source_ingestion_timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }


