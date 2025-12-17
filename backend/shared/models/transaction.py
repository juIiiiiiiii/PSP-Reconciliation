"""
Normalized Transaction Model
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    """Transaction status"""
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReconciliationStatus(str, Enum):
    """Reconciliation status"""
    PENDING = "PENDING"
    MATCHED = "MATCHED"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    UNMATCHED = "UNMATCHED"
    EXPECTED = "EXPECTED"
    POSTED = "POSTED"
    VOIDED = "VOIDED"


class EventType(str, Enum):
    """Transaction event types"""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"
    CHARGEBACK_REVERSAL = "CHARGEBACK_REVERSAL"
    FEE = "FEE"
    ROLLING_RESERVE = "ROLLING_RESERVE"
    PARTIAL_CAPTURE = "PARTIAL_CAPTURE"
    SPLIT_SETTLEMENT = "SPLIT_SETTLEMENT"
    NEGATIVE_SETTLEMENT = "NEGATIVE_SETTLEMENT"
    FX_CONVERSION = "FX_CONVERSION"


@dataclass
class Amount:
    """Amount with currency and FX information"""
    value: int  # in cents/smallest unit
    currency: str  # ISO 4217
    original_currency: Optional[str] = None
    fx_rate: Optional[Decimal] = None
    fx_rate_source: Optional[str] = None
    fx_rate_date: Optional[date] = None


@dataclass
class PSPReferences:
    """PSP-provided references"""
    psp_transaction_id: str
    psp_payment_id: Optional[str] = None
    psp_settlement_id: Optional[str] = None
    psp_batch_id: Optional[str] = None


@dataclass
class CustomerReferences:
    """Customer/player references"""
    customer_id: Optional[str] = None
    player_id: Optional[str] = None
    game_session_id: Optional[str] = None


@dataclass
class Source:
    """Event source information"""
    type: str  # WEBHOOK, API, SFTP, EMAIL, MANUAL
    idempotency_key: str
    raw_event_id: Optional[UUID] = None
    raw_event_s3_path: Optional[str] = None
    ingestion_timestamp: Optional[datetime] = None


class NormalizedTransaction(BaseModel):
    """Normalized transaction event (canonical schema)"""
    
    transaction_id: UUID
    tenant_id: UUID
    brand_id: UUID
    entity_id: UUID
    psp_connection_id: str
    event_type: EventType
    event_timestamp: datetime
    transaction_date: date
    amount_value: int = Field(..., description="Amount in cents")
    amount_currency: str = Field(..., max_length=3)
    amount_original_currency: Optional[str] = None
    amount_fx_rate: Optional[Decimal] = None
    amount_fx_rate_source: Optional[str] = None
    amount_fx_rate_date: Optional[date] = None
    psp_transaction_id: str
    psp_payment_id: Optional[str] = None
    psp_settlement_id: Optional[str] = None
    psp_batch_id: Optional[str] = None
    customer_id: Optional[str] = None
    player_id: Optional[str] = None
    game_session_id: Optional[str] = None
    psp_fee: Optional[int] = None  # cents
    fx_fee: Optional[int] = None  # cents
    net_amount: Optional[int] = None  # cents
    status: TransactionStatus
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.PENDING
    source_type: str
    source_idempotency_key: str
    source_raw_event_id: Optional[UUID] = None
    source_raw_event_s3_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    schema_version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: float,
        }


