"""
Tenant Hierarchy Models
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class ConnectorType(str, Enum):
    """PSP connector types"""
    WEBHOOK = "WEBHOOK"
    API_POLLING = "API_POLLING"
    SFTP = "SFTP"
    EMAIL = "EMAIL"
    MANUAL = "MANUAL"


class Tenant(BaseModel):
    """Tenant (operator)"""
    
    tenant_id: UUID
    tenant_name: str
    tenant_code: str
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class Brand(BaseModel):
    """Brand under a tenant"""
    
    brand_id: UUID
    tenant_id: UUID
    brand_name: str
    brand_code: str
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class Entity(BaseModel):
    """Entity (legal entity, jurisdiction)"""
    
    entity_id: UUID
    brand_id: UUID
    entity_name: str
    entity_code: str
    jurisdiction: Optional[str] = None
    base_currency: str = Field(..., max_length=3)
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class PSPConnection(BaseModel):
    """PSP connection configuration"""
    
    psp_connection_id: str
    tenant_id: UUID
    entity_id: Optional[UUID] = None
    psp_name: str
    connector_type: ConnectorType
    endpoint_url: Optional[str] = None
    authentication_type: Optional[str] = None
    authentication_secret_arn: Optional[str] = None
    webhook_signature_secret_arn: Optional[str] = None
    parser_version: Optional[str] = None
    schema_version: int = 1
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


