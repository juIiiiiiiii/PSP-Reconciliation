"""
Security tests for input validation
"""

import pytest
from fastapi.testclient import TestClient
from backend.services.api.main import app


class TestInputValidation:
    """Test input validation and SQL injection prevention"""
    
    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)
    
    def test_sql_injection_prevention(self, client):
        """Test SQL injection prevention"""
        # Attempt SQL injection in query parameter
        malicious_input = "'; DROP TABLE normalized_transaction; --"
        
        # Should be sanitized/validated by Pydantic/FastAPI
        response = client.get(
            f"/api/v1/reconciliations/stats?start_date={malicious_input}&end_date=2024-01-31",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Should return validation error, not execute SQL
        assert response.status_code in [400, 401, 422]
    
    def test_xss_prevention(self, client):
        """Test XSS prevention"""
        # Attempt XSS in request body
        malicious_input = "<script>alert('XSS')</script>"
        
        response = client.post(
            "/api/v1/matches/manual",
            json={
                "transaction_id": malicious_input,
                "settlement_id": "test-set-456",
                "notes": malicious_input
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Should sanitize or reject malicious input
        assert response.status_code in [400, 401, 422]


