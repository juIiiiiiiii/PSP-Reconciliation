"""
Load testing scripts
"""

import pytest
from locust import HttpUser, task, between


class ReconciliationPlatformUser(HttpUser):
    """Locust user for load testing"""
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login and get auth token"""
        # TODO: Implement authentication
        self.token = None
    
    @task(3)
    def get_reconciliation_stats(self):
        """Get reconciliation statistics"""
        self.client.get(
            "/api/v1/reconciliations/stats?start_date=2024-01-01&end_date=2024-01-31",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(2)
    def list_exceptions(self):
        """List exceptions"""
        self.client.get(
            "/api/v1/exceptions",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(1)
    def create_manual_match(self):
        """Create manual match"""
        self.client.post(
            "/api/v1/matches/manual",
            json={
                "transaction_id": "test-txn-123",
                "settlement_id": "test-set-456",
                "notes": "Manual match"
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )


# Run with: locust -f backend/tests/performance/test_load.py --host=http://localhost:8000


