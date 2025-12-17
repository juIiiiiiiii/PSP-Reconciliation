"""
Contract tests for API
"""

import pytest
from fastapi.testclient import TestClient
from backend.services.api.main import app


class TestAPIContracts:
    """Test API contracts"""
    
    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_api_openapi_schema(self, client):
        """Test OpenAPI schema is valid"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert 'openapi' in schema
        assert 'paths' in schema
        assert '/api/v1/reconciliations/stats' in schema['paths']
    
    def test_api_endpoints_require_authentication(self, client):
        """Test that protected endpoints require authentication"""
        response = client.get("/api/v1/reconciliations/stats?start_date=2024-01-01&end_date=2024-01-31")
        assert response.status_code == 401  # Unauthorized


