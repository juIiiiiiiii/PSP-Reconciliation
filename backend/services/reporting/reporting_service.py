"""
Reporting Service - Generates KPIs, reports, and analytics
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class ReportingService:
    """Generates reconciliation reports and KPIs"""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
    
    async def get_reconciliation_stats(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Get reconciliation statistics
        
        KPIs:
        - Match rate: (MATCHED / Total) * 100
        - Reconciliation completeness: (Settled / Expected) * 100
        - Exception count and value
        - Aged exceptions (> 7 days, > 30 days)
        """
        with self.SessionLocal() as session:
            # Get transaction counts
            stats = session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_transactions,
                        COUNT(*) FILTER (WHERE reconciliation_status = 'MATCHED') as matched_count,
                        COUNT(*) FILTER (WHERE reconciliation_status = 'UNMATCHED') as unmatched_count,
                        COUNT(*) FILTER (WHERE reconciliation_status = 'PARTIAL_MATCH') as partial_match_count,
                        COALESCE(SUM(amount_value) FILTER (
                            WHERE reconciliation_status IN ('UNMATCHED', 'PARTIAL_MATCH')
                        ), 0) as total_exception_value
                    FROM normalized_transaction
                    WHERE tenant_id = :tenant_id
                    AND transaction_date BETWEEN :start_date AND :end_date
                """),
                {
                    'tenant_id': str(tenant_id),
                    'start_date': start_date,
                    'end_date': end_date
                }
            ).fetchone()
            
            total = stats[0] or 0
            matched = stats[1] or 0
            match_rate = (matched / total * 100) if total > 0 else 0
            
            # Get aged exceptions
            aged_exceptions = await self._get_aged_exceptions(session, tenant_id)
            
            return {
                'total_transactions': total,
                'matched_count': matched,
                'unmatched_count': stats[2] or 0,
                'partial_match_count': stats[3] or 0,
                'match_rate': round(match_rate, 2),
                'total_exception_value': stats[4] or 0,
                'aged_exceptions_7_days': aged_exceptions.get('7_days', 0),
                'aged_exceptions_30_days': aged_exceptions.get('30_days', 0)
            }
    
    async def _get_aged_exceptions(
        self,
        session,
        tenant_id: UUID
    ) -> Dict:
        """Get aged exceptions count"""
        result = session.execute(
            text("""
                SELECT 
                    COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '7 days') as aged_7_days,
                    COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '30 days') as aged_30_days
                FROM reconciliation_exception
                WHERE tenant_id = :tenant_id
                AND status = 'OPEN'
            """),
            {'tenant_id': str(tenant_id)}
        ).fetchone()
        
        return {
            '7_days': result[0] or 0,
            '30_days': result[1] or 0
        }
    
    async def generate_daily_reconciliation_report(
        self,
        tenant_id: UUID,
        report_date: date
    ) -> Dict:
        """
        Generate daily reconciliation report
        
        Includes:
        - Summary: Total transactions, matched, exceptions
        - Exception list (sorted by amount)
        - Settlement summary per PSP
        - Alerts: Threshold breaches
        """
        stats = await self.get_reconciliation_stats(
            tenant_id, report_date, report_date
        )
        
        # Get exceptions
        exceptions = await self._get_exceptions_for_date(
            tenant_id, report_date
        )
        
        # Get settlement summary
        settlement_summary = await self._get_settlement_summary(
            tenant_id, report_date
        )
        
        # Check thresholds
        alerts = await self._check_thresholds(stats)
        
        return {
            'report_date': report_date.isoformat(),
            'summary': stats,
            'exceptions': exceptions,
            'settlement_summary': settlement_summary,
            'alerts': alerts
        }
    
    async def _get_exceptions_for_date(
        self,
        tenant_id: UUID,
        report_date: date
    ) -> List[Dict]:
        """Get exceptions for specific date"""
        with self.SessionLocal() as session:
            results = session.execute(
                text("""
                    SELECT 
                        e.exception_id,
                        e.transaction_id,
                        e.exception_type,
                        e.amount_value,
                        e.amount_currency,
                        e.priority,
                        e.status,
                        t.psp_transaction_id,
                        t.psp_connection_id
                    FROM reconciliation_exception e
                    JOIN normalized_transaction t ON e.transaction_id = t.transaction_id
                    WHERE e.tenant_id = :tenant_id
                    AND t.transaction_date = :report_date
                    ORDER BY e.amount_value DESC
                """),
                {
                    'tenant_id': str(tenant_id),
                    'report_date': report_date
                }
            ).fetchall()
            
            return [
                {
                    'exception_id': str(row[0]),
                    'transaction_id': str(row[1]),
                    'exception_type': row[2],
                    'amount_value': row[3],
                    'amount_currency': row[4],
                    'priority': row[5],
                    'status': row[6],
                    'psp_transaction_id': row[7],
                    'psp_connection_id': row[8]
                }
                for row in results
            ]
    
    async def _get_settlement_summary(
        self,
        tenant_id: UUID,
        report_date: date
    ) -> List[Dict]:
        """Get settlement summary per PSP"""
        with self.SessionLocal() as session:
            results = session.execute(
                text("""
                    SELECT 
                        psp_connection_id,
                        COUNT(*) as settlement_count,
                        SUM(amount_value) as total_amount,
                        SUM(psp_fee) as total_fees,
                        SUM(net_amount) as net_amount
                    FROM psp_settlement
                    WHERE tenant_id = :tenant_id
                    AND settlement_date = :report_date
                    GROUP BY psp_connection_id
                """),
                {
                    'tenant_id': str(tenant_id),
                    'report_date': report_date
                }
            ).fetchall()
            
            return [
                {
                    'psp_connection_id': row[0],
                    'settlement_count': row[1],
                    'total_amount': row[2],
                    'total_fees': row[3],
                    'net_amount': row[4]
                }
                for row in results
            ]
    
    async def _check_thresholds(self, stats: Dict) -> List[Dict]:
        """Check reconciliation thresholds and generate alerts"""
        alerts = []
        
        # Match rate threshold
        if stats['match_rate'] < 95:
            alerts.append({
                'level': 'P1',
                'type': 'LOW_MATCH_RATE',
                'message': f"Match rate below threshold: {stats['match_rate']}%"
            })
        elif stats['match_rate'] < 99:
            alerts.append({
                'level': 'P2',
                'type': 'LOW_MATCH_RATE',
                'message': f"Match rate below target: {stats['match_rate']}%"
            })
        
        # Exception value threshold
        if stats['total_exception_value'] >= 1000000:  # >= $10,000
            alerts.append({
                'level': 'P1',
                'type': 'HIGH_EXCEPTION_VALUE',
                'message': f"Exception value exceeds threshold: ${stats['total_exception_value'] / 100}"
            })
        elif stats['total_exception_value'] >= 100000:  # >= $1,000
            alerts.append({
                'level': 'P2',
                'type': 'HIGH_EXCEPTION_VALUE',
                'message': f"Exception value high: ${stats['total_exception_value'] / 100}"
            })
        
        # Aged exceptions
        if stats['aged_exceptions_30_days'] > 0:
            alerts.append({
                'level': 'P1',
                'type': 'AGED_EXCEPTIONS',
                'message': f"{stats['aged_exceptions_30_days']} exceptions aged > 30 days"
            })
        elif stats['aged_exceptions_7_days'] > 0:
            alerts.append({
                'level': 'P2',
                'type': 'AGED_EXCEPTIONS',
                'message': f"{stats['aged_exceptions_7_days']} exceptions aged > 7 days"
            })
        
        return alerts


