"""
Adyen Parser - Parses Adyen webhooks and settlement files
"""

import csv
import io
import json
from typing import List, Dict, Any
from datetime import datetime

from services.ingestion.parsers.base import BaseParser
from shared.models.transaction import EventType


class AdyenParser(BaseParser):
    """Parser for Adyen events and settlement files"""
    
    def __init__(self, version: str = "v1.5"):
        super().__init__(version)
        self.psp_name = "adyen"
    
    async def parse(
        self,
        content: bytes,
        file_format: str
    ) -> List[Dict[str, Any]]:
        """Parse Adyen content"""
        if file_format == 'JSON':
            return await self._parse_json(content)
        elif file_format == 'CSV':
            return await self._parse_csv(content)
        else:
            raise ValueError(f"Unsupported format for Adyen: {file_format}")
    
    async def _parse_json(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse Adyen webhook JSON"""
        data = json.loads(content)
        
        # Adyen notification format
        if 'notificationItems' in data:
            events = []
            for item in data['notificationItems']:
                notification = item.get('NotificationRequestItem', {})
                events.append({
                    'psp_event_id': notification.get('pspReference'),
                    'psp_event_type': notification.get('eventCode'),
                    'event_type': self.normalize_event_type(notification.get('eventCode', '')),
                    'data': notification,
                    'event_date': notification.get('eventDate')
                })
            return events
        else:
            # Single notification
            return [{
                'psp_event_id': data.get('pspReference'),
                'psp_event_type': data.get('eventCode'),
                'event_type': self.normalize_event_type(data.get('eventCode', '')),
                'data': data,
                'event_date': data.get('eventDate')
            }]
    
    async def _parse_csv(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse Adyen settlement CSV"""
        text = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        
        events = []
        for row in reader:
            # Map Adyen CSV columns to normalized format
            event = {
                'psp_transaction_id': row.get('Merchant Reference'),
                'psp_payment_id': row.get('Payment Reference'),
                'amount': int(float(row.get('Amount', 0)) * 100),  # Convert to cents
                'currency': row.get('Currency', 'EUR').upper(),
                'status': row.get('Type'),
                'created': row.get('Creation Date'),
                'fee': int(float(row.get('Commission', 0)) * 100),
                'net': int(float(row.get('Net Amount', 0)) * 100),
                'event_type': 'SETTLEMENT'
            }
            events.append(event)
        
        return events
    
    def normalize_event_type(self, psp_event_type: str) -> str:
        """Map Adyen event codes to canonical types"""
        mapping = {
            'AUTHORISATION': EventType.DEPOSIT,
            'CAPTURE': EventType.DEPOSIT,
            'REFUND': EventType.REFUND,
            'CHARGEBACK': EventType.CHARGEBACK,
            'CHARGEBACK_REVERSED': EventType.CHARGEBACK_REVERSAL,
            'PAYOUT': EventType.SETTLEMENT,
        }
        
        return mapping.get(psp_event_type, psp_event_type.upper())
    
    def validate(self, event: Dict[str, Any]) -> bool:
        """Validate Adyen event"""
        required_fields = ['psp_event_id', 'event_type']
        return all(field in event for field in required_fields)


