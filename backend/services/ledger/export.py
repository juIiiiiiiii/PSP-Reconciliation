"""
Ledger Export Service - Exports ledger entries to external systems
"""

import csv
import io
import logging
from datetime import date
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class LedgerExportService:
    """Exports ledger entries to NetSuite, SAP, QuickBooks, etc."""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
    
    async def export_netsuite(
        self,
        tenant_id: UUID,
        entity_id: UUID,
        start_date: date,
        end_date: date
    ) -> str:
        """
        Export ledger entries in NetSuite format (CSV)
        
        Format: Date, Account, Debit, Credit, Memo, Custom Fields
        """
        with self.SessionLocal() as session:
            entries = session.execute(
                text("""
                    SELECT 
                        transaction_date,
                        account_debit,
                        account_credit,
                        amount,
                        currency,
                        description
                    FROM ledger_entry
                    WHERE tenant_id = :tenant_id
                    AND entity_id = :entity_id
                    AND transaction_date BETWEEN :start_date AND :end_date
                    ORDER BY transaction_date, ledger_entry_id
                """),
                {
                    'tenant_id': str(tenant_id),
                    'entity_id': str(entity_id),
                    'start_date': start_date,
                    'end_date': end_date
                }
            ).fetchall()
            
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'Date', 'Account', 'Debit', 'Credit', 'Memo', 'Currency'
            ])
            
            # Rows (split each entry into debit and credit rows)
            for entry in entries:
                # Debit row
                writer.writerow([
                    entry[0].strftime('%Y-%m-%d'),
                    entry[1],  # account_debit
                    entry[3] / 100.0,  # amount (convert from cents)
                    0,  # credit
                    entry[5],  # description
                    entry[4]  # currency
                ])
                
                # Credit row
                writer.writerow([
                    entry[0].strftime('%Y-%m-%d'),
                    entry[2],  # account_credit
                    0,  # debit
                    entry[3] / 100.0,  # amount (convert from cents)
                    entry[5],  # description
                    entry[4]  # currency
                ])
            
            return output.getvalue()
    
    async def export_sap(
        self,
        tenant_id: UUID,
        entity_id: UUID,
        start_date: date,
        end_date: date
    ) -> str:
        """
        Export ledger entries in SAP IDoc format (XML) or CSV
        """
        # Similar to NetSuite but with SAP-specific format
        # For now, return CSV format
        return await self.export_netsuite(tenant_id, entity_id, start_date, end_date)
    
    async def export_quickbooks(
        self,
        tenant_id: UUID,
        entity_id: UUID,
        start_date: date,
        end_date: date
    ) -> str:
        """
        Export ledger entries in QuickBooks IIF format or CSV
        """
        # Similar to NetSuite but with QuickBooks-specific format
        # For now, return CSV format
        return await self.export_netsuite(tenant_id, entity_id, start_date, end_date)
    
    async def export_custom(
        self,
        tenant_id: UUID,
        entity_id: UUID,
        start_date: date,
        end_date: date,
        template: Dict[str, Any]
    ) -> str:
        """
        Export ledger entries using custom template
        
        Template defines field mapping and format
        """
        # Implement custom template-based export
        pass


