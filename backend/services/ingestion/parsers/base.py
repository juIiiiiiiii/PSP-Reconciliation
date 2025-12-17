"""
Base Parser Interface
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Base class for PSP-specific parsers"""
    
    def __init__(self, version: str):
        self.version = version
    
    @abstractmethod
    async def parse(
        self,
        content: bytes,
        file_format: str
    ) -> List[Dict[str, Any]]:
        """
        Parse file/content and return list of normalized events
        
        Args:
            content: File content (bytes)
            file_format: Format (CSV, XLSX, JSON, PDF)
        
        Returns:
            List of normalized event dictionaries
        """
        pass
    
    @abstractmethod
    def validate(self, event: Dict[str, Any]) -> bool:
        """Validate parsed event against schema"""
        pass
    
    def normalize_event_type(self, psp_event_type: str) -> str:
        """Map PSP-specific event type to canonical type"""
        # Default implementation - override in subclasses
        return psp_event_type.upper()


