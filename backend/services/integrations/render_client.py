"""
Render Integration Client
Provides deployment and service management
"""

import logging
import os
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)


class RenderClient:
    """Render integration for deployment"""
    
    def __init__(
        self,
        api_key: Optional[str] = None
    ):
        """
        Initialize Render client
        
        Args:
            api_key: Render API key
        """
        self.api_key = api_key or os.getenv('RENDER_API_KEY')
        self.base_url = "https://api.render.com/v1"
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        } if self.api_key else {}
    
    async def list_services_via_mcp(
        self,
        owner_id: Optional[str] = None,
        service_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List Render services via MCP tool
        
        This would be called via MCP tool, not directly
        """
        logger.info("Render services would be listed via MCP")
        return []
    
    def get_service_url(self, service_id: str) -> Optional[str]:
        """Get service URL from Render"""
        if not self.api_key:
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/services/{service_id}",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return data.get('service', {}).get('serviceDetails', {}).get('url')
        except Exception as e:
            logger.error(f"Error getting Render service URL: {str(e)}")
            return None


