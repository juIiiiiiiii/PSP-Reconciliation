"""
User and RBAC Models
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class UserRole(str, Enum):
    """User roles (hierarchical)"""
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    FINANCE_DIRECTOR = "FINANCE_DIRECTOR"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    RECONCILIATION_ANALYST = "RECONCILIATION_ANALYST"
    AUDITOR = "AUDITOR"


class SSOProvider(str, Enum):
    """SSO provider types"""
    AWS_SSO = "AWS_SSO"
    OKTA = "OKTA"
    AZURE_AD = "AZURE_AD"
    OIDC = "OIDC"


class User(BaseModel):
    """User with RBAC"""
    
    user_id: UUID
    tenant_id: Optional[UUID] = None  # NULL for platform admins
    email: str
    full_name: Optional[str] = None
    role: UserRole
    sso_provider: Optional[SSOProvider] = None
    sso_external_id: Optional[str] = None
    mfa_enabled: bool = False
    status: str = "ACTIVE"
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


