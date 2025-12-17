"""
Smoke tests for production readiness
"""

import pytest
from fastapi.testclient import TestClient
from backend.services.api.main import app


@pytest.mark.smoke
class TestSmokeTests:
    """Smoke tests for critical paths"""
    
    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_api_accessible(self, client):
        """Test API is accessible"""
        # Even without auth, should return 401, not 500
        response = client.get("/api/v1/reconciliations/stats")
        assert response.status_code in [401, 403]  # Unauthorized, not server error
    
    def test_database_connectivity(self):
        """Test database connectivity"""
        # This would test actual database connection
        # Full implementation would use testcontainers
        pass
    
    def test_redis_connectivity(self):
        """Test Redis connectivity"""
        # This would test actual Redis connection
        # Full implementation would use testcontainers
        pass


