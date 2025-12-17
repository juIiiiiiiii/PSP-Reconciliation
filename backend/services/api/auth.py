"""
Authentication and Authorization - RBAC and SSO
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import jwt
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.models.user import User, UserRole

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AuthService:
    """Handles authentication and authorization"""
    
    def __init__(self, jwt_secret: str, sso_providers: dict):
        self.jwt_secret = jwt_secret
        self.sso_providers = sso_providers
    
    async def verify_token(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict:
        """Verify JWT token and extract claims"""
        try:
            token = credentials.credentials
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    async def get_current_user(
        self,
        token: dict = Depends(verify_token)
    ) -> User:
        """Get current user from token"""
        user_id = UUID(token.get('user_id'))
        tenant_id = UUID(token.get('tenant_id')) if token.get('tenant_id') else None
        role = UserRole(token.get('role'))
        
        # TODO: Load full user from database
        return User(
            user_id=user_id,
            tenant_id=tenant_id,
            email=token.get('email', ''),
            role=role,
            status='ACTIVE'
        )
    
    def check_permission(
        self,
        user: User,
        required_permission: str,
        resource_tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if user has required permission
        
        Permission hierarchy:
        - Platform Admin: All permissions
        - Tenant Admin: All tenant permissions
        - Finance Director: Financial operations
        - Finance Manager: View and approve < $10k
        - Reconciliation Analyst: View and investigate
        - Auditor: Read-only
        """
        # Platform admins have all permissions
        if user.role == UserRole.PLATFORM_ADMIN:
            return True
        
        # Tenant isolation: users can only access their tenant's data
        if resource_tenant_id and user.tenant_id != resource_tenant_id:
            return False
        
        # Permission matrix
        permissions = {
            UserRole.TENANT_ADMIN: [
                'view_reconciliations', 'investigate_exceptions',
                'create_manual_matches', 'approve_adjustments',
                'configure_rules', 'export_ledger', 'trigger_reprocessing',
                'manage_users'
            ],
            UserRole.FINANCE_DIRECTOR: [
                'view_reconciliations', 'investigate_exceptions',
                'create_manual_matches', 'approve_adjustments',
                'configure_rules', 'export_ledger', 'trigger_reprocessing'
            ],
            UserRole.FINANCE_MANAGER: [
                'view_reconciliations', 'investigate_exceptions',
                'create_manual_matches', 'approve_adjustments_under_10k',
                'export_ledger', 'trigger_reprocessing'
            ],
            UserRole.RECONCILIATION_ANALYST: [
                'view_reconciliations', 'investigate_exceptions',
                'create_manual_matches', 'trigger_reprocessing'
            ],
            UserRole.AUDITOR: [
                'view_reconciliations', 'view_audit_logs', 'export_reports'
            ]
        }
        
        user_permissions = permissions.get(user.role, [])
        return required_permission in user_permissions
    
    async def sso_callback(
        self,
        provider: str,
        assertion: dict
    ) -> dict:
        """
        Handle SSO callback (SAML/OIDC)
        
        Steps:
        1. Validate assertion
        2. Extract user attributes
        3. Map SSO groups to internal roles
        4. Create/update user
        5. Generate JWT token
        """
        # Validate assertion with SSO provider
        sso_provider = self.sso_providers.get(provider)
        if not sso_provider:
            raise HTTPException(status_code=400, detail=f"Unknown SSO provider: {provider}")
        
        # Extract user attributes
        email = assertion.get('email')
        groups = assertion.get('groups', [])
        
        # Map SSO groups to internal roles
        role = self._map_sso_groups_to_role(groups, provider)
        
        # Get or create user
        user = await self._get_or_create_user(email, role, provider, assertion.get('external_id'))
        
        # Generate JWT token
        token = self._generate_jwt_token(user)
        
        return {
            'access_token': token,
            'token_type': 'bearer',
            'user': {
                'user_id': str(user.user_id),
                'email': user.email,
                'role': user.role.value,
                'tenant_id': str(user.tenant_id) if user.tenant_id else None
            }
        }
    
    def _map_sso_groups_to_role(self, groups: list, provider: str) -> UserRole:
        """Map SSO groups to internal roles"""
        # Default mapping - should be configurable per tenant
        role_mapping = {
            'finance-director': UserRole.FINANCE_DIRECTOR,
            'finance-manager': UserRole.FINANCE_MANAGER,
            'reconciliation-analyst': UserRole.RECONCILIATION_ANALYST,
            'auditor': UserRole.AUDITOR,
            'admin': UserRole.TENANT_ADMIN
        }
        
        for group in groups:
            if group.lower() in role_mapping:
                return role_mapping[group.lower()]
        
        # Default to auditor (least privilege)
        return UserRole.AUDITOR
    
    async def _get_or_create_user(
        self,
        email: str,
        role: UserRole,
        sso_provider: str,
        external_id: Optional[str]
    ) -> User:
        """Get or create user from SSO"""
        # TODO: Implement database lookup/creation
        from uuid import uuid4
        return User(
            user_id=uuid4(),
            email=email,
            role=role,
            sso_provider=sso_provider,
            sso_external_id=external_id,
            status='ACTIVE'
        )
    
    def _generate_jwt_token(self, user: User) -> str:
        """Generate JWT token for user"""
        payload = {
            'user_id': str(user.user_id),
            'email': user.email,
            'role': user.role.value,
            'tenant_id': str(user.tenant_id) if user.tenant_id else None,
            'exp': datetime.utcnow() + timedelta(hours=8)  # 8 hour session
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")


def require_permission(permission: str):
    """Dependency to require specific permission"""
    async def permission_checker(
        user: User = Depends(AuthService.get_current_user)
    ) -> User:
        auth_service = AuthService("", {})  # TODO: Get from app context
        if not auth_service.check_permission(user, permission):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return permission_checker

