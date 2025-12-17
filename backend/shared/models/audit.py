"""
Audit Log Model
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class AuditLog(BaseModel):
    """Append-only audit log entry"""
    
    audit_log_id: UUID
    tenant_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: str  # CREATE, UPDATE, DELETE, APPROVE, EXPORT, LOGIN, etc.
    resource_type: str  # TRANSACTION, MATCH, ADJUSTMENT, USER, etc.
    resource_id: Optional[UUID] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


