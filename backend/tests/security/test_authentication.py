"""
Security tests for authentication and authorization
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.services.api.main import app
from backend.services.api.auth import AuthService


class TestAuthentication:
    """Test authentication"""
    
    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)
    
    @pytest.fixture
    def auth_service(self):
        """Auth service"""
        return AuthService(jwt_secret="test-secret", sso_providers={})
    
    def test_jwt_token_validation(self, auth_service):
        """Test JWT token validation"""
        # Create valid token
        user = type('obj', (object,), {
            'user_id': uuid4(),
            'email': 'test@example.com',
            'role': 'FINANCE_MANAGER',
            'tenant_id': uuid4()
        })()
        
        token = auth_service._generate_jwt_token(user)
        
        # Verify token
        payload = auth_service.verify_token(
            type('obj', (object,), {'credentials': token})()
        )
        
        assert payload['email'] == 'test@example.com'
        assert payload['role'] == 'FINANCE_MANAGER'
    
    def test_rbac_permission_checking(self, auth_service):
        """Test RBAC permission checking"""
        user = type('obj', (object,), {
            'user_id': uuid4(),
            'role': 'FINANCE_MANAGER',
            'tenant_id': uuid4()
        })()
        
        # Finance Manager should have view_reconciliations
        assert auth_service.check_permission(user, 'view_reconciliations') is True
        
        # Finance Manager should NOT have configure_connectors
        assert auth_service.check_permission(user, 'configure_connectors') is False
    
    def test_tenant_isolation(self, auth_service):
        """Test tenant isolation"""
        user = type('obj', (object,), {
            'user_id': uuid4(),
            'role': 'FINANCE_MANAGER',
            'tenant_id': uuid4()
        })()
        
        resource_tenant_id = uuid4()  # Different tenant
        
        # Should be denied access to different tenant
        assert auth_service.check_permission(
            user, 'view_reconciliations', resource_tenant_id
        ) is False

