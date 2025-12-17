"""
Reconciliation Matching Engine
Implements hierarchical matching: Strong ID → PSP Reference → Fuzzy → Amount+Date
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.models.match import (
    ReconciliationMatch,
    MatchLevel,
    MatchMethod,
    MatchStatus
)
from shared.models.exception import (
    ReconciliationException,
    ExceptionType,
    ExceptionPriority,
    ExceptionStatus
)

logger = logging.getLogger(__name__)


class MatchResult:
    """Result of matching attempt"""
    def __init__(
        self,
        status: MatchStatus,
        confidence: float,
        match: Optional[ReconciliationMatch] = None,
        exception: Optional[ReconciliationException] = None
    ):
        self.status = status
        self.confidence = confidence
        self.match = match
        self.exception = exception


class MatchingEngine:
    """Reconciliation matching engine with hierarchical matching"""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
    
    async def match_transaction(
        self,
        transaction_id: UUID
    ) -> MatchResult:
        """
        Match a transaction against settlements using hierarchical matching
        
        Matching hierarchy:
        1. Level 1: Strong ID (psp_connection_id + psp_transaction_id + psp_settlement_id)
        2. Level 2: PSP Reference (psp_payment_id + amount + currency + date)
        3. Level 3: Fuzzy (amount + currency + date ± 1 day + customer_id)
        4. Level 4: Amount + Date (amount + currency + date)
        """
        with self.SessionLocal() as session:
            # Get transaction
            transaction = self._get_transaction(session, transaction_id)
            if not transaction:
                raise ValueError(f"Transaction not found: {transaction_id}")
            
            # Skip if already matched
            if transaction['reconciliation_status'] == 'MATCHED':
                return MatchResult(
                    status=MatchStatus.MATCHED,
                    confidence=100.0,
                    match=None  # Already matched
                )
            
            # Level 1: Strong ID Match
            match = await self._match_level_1(session, transaction)
            if match:
                return MatchResult(
                    status=MatchStatus.MATCHED,
                    confidence=100.0,
                    match=match
                )
            
            # Level 2: PSP Reference Match
            match = await self._match_level_2(session, transaction)
            if match:
                # Check amount difference
                amount_diff_pct = abs(match.amount_difference_percent or 0)
                if amount_diff_pct < 1.0:  # Less than 1% difference
                    return MatchResult(
                        status=MatchStatus.MATCHED,
                        confidence=95.0,
                        match=match
                    )
                else:
                    # Amount mismatch - create exception
                    return MatchResult(
                        status=MatchStatus.PARTIAL_MATCH,
                        confidence=95.0,
                        match=match,
                        exception=self._create_exception(
                            session, transaction, ExceptionType.AMOUNT_MISMATCH, match
                        )
                    )
            
            # Level 3: Fuzzy Match
            match = await self._match_level_3(session, transaction)
            if match:
                return MatchResult(
                    status=MatchStatus.PARTIAL_MATCH,
                    confidence=match.confidence_score,
                    match=match,
                    exception=self._create_exception(
                        session, transaction, ExceptionType.PARTIAL_MATCH, match
                    )
                )
            
            # Level 4: Amount + Date Match
            match = await self._match_level_4(session, transaction)
            if match:
                return MatchResult(
                    status=MatchStatus.PENDING_REVIEW,
                    confidence=match.confidence_score,
                    match=match,
                    exception=self._create_exception(
                        session, transaction, ExceptionType.PARTIAL_MATCH, match
                    )
                )
            
            # No match found - create exception
            exception = self._create_exception(
                session, transaction, ExceptionType.UNMATCHED, None
            )
            return MatchResult(
                status=MatchStatus.UNMATCHED,
                confidence=0.0,
                match=None,
                exception=exception
            )
    
    async def _match_level_1(
        self,
        session,
        transaction: dict
    ) -> Optional[ReconciliationMatch]:
        """Level 1: Strong ID Match (100% confidence)"""
        if not transaction.get('psp_settlement_id'):
            return None
        
        # Find settlement with matching IDs
        settlement = session.execute(
            text("""
                SELECT settlement_id, amount_value, amount_currency
                FROM psp_settlement
                WHERE tenant_id = :tenant_id
                AND psp_connection_id = :psp_conn
                AND psp_settlement_id = :psp_settlement_id
                AND settlement_date = :settlement_date
                AND NOT EXISTS (
                    SELECT 1 FROM reconciliation_match
                    WHERE settlement_id = psp_settlement.settlement_id
                    AND status = 'MATCHED'
                )
            """),
            {
                'tenant_id': str(transaction['tenant_id']),
                'psp_conn': transaction['psp_connection_id'],
                'psp_settlement_id': transaction['psp_settlement_id'],
                'settlement_date': transaction['transaction_date']
            }
        ).fetchone()
        
        if settlement:
            return await self._create_match(
                session, transaction, UUID(settlement[0]),
                MatchLevel.STRONG_ID, MatchMethod.AUTO, 100.0
            )
        
        return None
    
    async def _match_level_2(
        self,
        session,
        transaction: dict
    ) -> Optional[ReconciliationMatch]:
        """Level 2: PSP Reference Match (95% confidence)"""
        if not transaction.get('psp_payment_id'):
            return None
        
        # Find settlement with matching payment ID and amount
        settlement = session.execute(
            text("""
                SELECT s.settlement_id, s.amount_value, s.amount_currency
                FROM psp_settlement s
                WHERE s.tenant_id = :tenant_id
                AND s.psp_connection_id = :psp_conn
                AND :psp_payment_id = ANY(s.psp_transaction_ids)
                AND s.settlement_date = :transaction_date
                AND s.amount_currency = :currency
                AND ABS(s.amount_value - :amount) <= :tolerance
                AND NOT EXISTS (
                    SELECT 1 FROM reconciliation_match
                    WHERE settlement_id = s.settlement_id
                    AND status = 'MATCHED'
                )
                LIMIT 1
            """),
            {
                'tenant_id': str(transaction['tenant_id']),
                'psp_conn': transaction['psp_connection_id'],
                'psp_payment_id': transaction['psp_payment_id'],
                'transaction_date': transaction['transaction_date'],
                'currency': transaction['amount_currency'],
                'amount': transaction['amount_value'],
                'tolerance': int(transaction['amount_value'] * 0.01)  # 1% tolerance
            }
        ).fetchone()
        
        if settlement:
            amount_diff = transaction['amount_value'] - settlement[1]
            amount_diff_pct = abs(amount_diff / transaction['amount_value'] * 100) if transaction['amount_value'] > 0 else 0
            
            return await self._create_match(
                session, transaction, UUID(settlement[0]),
                MatchLevel.PSP_REFERENCE, MatchMethod.AUTO, 95.0,
                amount_diff, amount_diff_pct
            )
        
        return None
    
    async def _match_level_3(
        self,
        session,
        transaction: dict
    ) -> Optional[ReconciliationMatch]:
        """Level 3: Fuzzy Match (70-90% confidence)"""
        # Match on: amount + currency + date ± 1 day + customer_id
        date_window_start = transaction['transaction_date'] - timedelta(days=1)
        date_window_end = transaction['transaction_date'] + timedelta(days=1)
        
        # Build query with optional customer_id
        query = """
            SELECT s.settlement_id, s.amount_value, s.amount_currency
            FROM psp_settlement s
            WHERE s.tenant_id = :tenant_id
            AND s.psp_connection_id = :psp_conn
            AND s.settlement_date BETWEEN :date_start AND :date_end
            AND s.amount_currency = :currency
            AND ABS(s.amount_value - :amount) <= :tolerance
            AND NOT EXISTS (
                SELECT 1 FROM reconciliation_match
                WHERE settlement_id = s.settlement_id
                AND status = 'MATCHED'
            )
        """
        
        params = {
            'tenant_id': str(transaction['tenant_id']),
            'psp_conn': transaction['psp_connection_id'],
            'date_start': date_window_start,
            'date_end': date_window_end,
            'currency': transaction['amount_currency'],
            'amount': transaction['amount_value'],
            'tolerance': int(transaction['amount_value'] * 0.001)  # 0.1% tolerance
        }
        
        # If customer_id available, prefer matches with same customer
        if transaction.get('customer_id'):
            query += " AND :customer_id = ANY(s.psp_transaction_ids)"
            params['customer_id'] = transaction['customer_id']
        
        query += " LIMIT 1"
        
        settlement = session.execute(text(query), params).fetchone()
        
        if settlement:
            # Calculate confidence based on date difference
            date_diff = abs((settlement[2] - transaction['transaction_date']).days)
            confidence = max(70.0, 90.0 - (date_diff * 10))  # Decrease by 10% per day
            
            amount_diff = transaction['amount_value'] - settlement[1]
            amount_diff_pct = abs(amount_diff / transaction['amount_value'] * 100) if transaction['amount_value'] > 0 else 0
            
            return await self._create_match(
                session, transaction, UUID(settlement[0]),
                MatchLevel.FUZZY, MatchMethod.AUTO, confidence,
                amount_diff, amount_diff_pct
            )
        
        return None
    
    async def _match_level_4(
        self,
        session,
        transaction: dict
    ) -> Optional[ReconciliationMatch]:
        """Level 4: Amount + Date Match (50-70% confidence)"""
        # Match on: amount + currency + date (exact)
        settlement = session.execute(
            text("""
                SELECT s.settlement_id, s.amount_value, s.amount_currency
                FROM psp_settlement s
                WHERE s.tenant_id = :tenant_id
                AND s.psp_connection_id = :psp_conn
                AND s.settlement_date = :transaction_date
                AND s.amount_currency = :currency
                AND s.amount_value = :amount
                AND NOT EXISTS (
                    SELECT 1 FROM reconciliation_match
                    WHERE settlement_id = s.settlement_id
                    AND status = 'MATCHED'
                )
                LIMIT 1
            """),
            {
                'tenant_id': str(transaction['tenant_id']),
                'psp_conn': transaction['psp_connection_id'],
                'transaction_date': transaction['transaction_date'],
                'currency': transaction['amount_currency'],
                'amount': transaction['amount_value']
            }
        ).fetchone()
        
        if settlement:
            return await self._create_match(
                session, transaction, UUID(settlement[0]),
                MatchLevel.AMOUNT_DATE, MatchMethod.AUTO, 60.0
            )
        
        return None
    
    async def _create_match(
        self,
        session,
        transaction: dict,
        settlement_id: UUID,
        match_level: MatchLevel,
        match_method: MatchMethod,
        confidence: float,
        amount_diff: Optional[int] = None,
        amount_diff_pct: Optional[float] = None
    ) -> ReconciliationMatch:
        """Create reconciliation match record"""
        from uuid import uuid4
        
        match_id = uuid4()
        
        session.execute(
            text("""
                INSERT INTO reconciliation_match (
                    match_id, tenant_id, transaction_id, settlement_id,
                    match_level, confidence_score, match_method,
                    amount_difference, amount_difference_percent,
                    status, matched_at
                ) VALUES (
                    :match_id, :tenant_id, :transaction_id, :settlement_id,
                    :match_level, :confidence_score, :match_method,
                    :amount_difference, :amount_difference_percent,
                    :status, NOW()
                )
                ON CONFLICT (tenant_id, transaction_id, settlement_id)
                DO NOTHING
            """),
            {
                'match_id': str(match_id),
                'tenant_id': str(transaction['tenant_id']),
                'transaction_id': str(transaction['transaction_id']),
                'settlement_id': str(settlement_id),
                'match_level': match_level.value,
                'confidence_score': confidence,
                'match_method': match_method.value,
                'amount_difference': amount_diff,
                'amount_difference_percent': amount_diff_pct,
                'status': MatchStatus.MATCHED.value if confidence >= 95.0 else MatchStatus.PARTIAL_MATCH.value
            }
        )
        
        # Update transaction reconciliation status
        session.execute(
            text("""
                UPDATE normalized_transaction
                SET reconciliation_status = :status
                WHERE transaction_id = :transaction_id
            """),
            {
                'transaction_id': str(transaction['transaction_id']),
                'status': MatchStatus.MATCHED.value if confidence >= 95.0 else 'PARTIAL_MATCH'
            }
        )
        
        session.commit()
        
        return ReconciliationMatch(
            match_id=match_id,
            tenant_id=UUID(transaction['tenant_id']),
            transaction_id=UUID(transaction['transaction_id']),
            settlement_id=settlement_id,
            match_level=match_level,
            confidence_score=Decimal(str(confidence)),
            match_method=match_method,
            amount_difference=amount_diff,
            amount_difference_percent=Decimal(str(amount_diff_pct)) if amount_diff_pct else None,
            matched_at=datetime.utcnow(),
            status=MatchStatus.MATCHED if confidence >= 95.0 else MatchStatus.PARTIAL_MATCH
        )
    
    def _create_exception(
        self,
        session,
        transaction: dict,
        exception_type: ExceptionType,
        match: Optional[ReconciliationMatch]
    ) -> ReconciliationException:
        """Create reconciliation exception"""
        from uuid import uuid4
        from datetime import datetime
        
        exception_id = uuid4()
        
        # Determine priority based on amount
        amount = transaction['amount_value']
        if amount >= 1000000:  # >= $10,000
            priority = ExceptionPriority.P1
        elif amount >= 100000:  # >= $1,000
            priority = ExceptionPriority.P2
        elif amount >= 10000:  # >= $100
            priority = ExceptionPriority.P3
        else:
            priority = ExceptionPriority.P4
        
        session.execute(
            text("""
                INSERT INTO reconciliation_exception (
                    exception_id, tenant_id, transaction_id, settlement_id,
                    exception_type, exception_reason,
                    amount_value, amount_currency,
                    priority, status, created_at
                ) VALUES (
                    :exception_id, :tenant_id, :transaction_id, :settlement_id,
                    :exception_type, :exception_reason,
                    :amount_value, :amount_currency,
                    :priority, :status, NOW()
                )
            """),
            {
                'exception_id': str(exception_id),
                'tenant_id': str(transaction['tenant_id']),
                'transaction_id': str(transaction['transaction_id']),
                'settlement_id': str(match.settlement_id) if match else None,
                'exception_type': exception_type.value,
                'exception_reason': self._get_exception_reason(exception_type, match),
                'amount_value': amount,
                'amount_currency': transaction['amount_currency'],
                'priority': priority.value,
                'status': ExceptionStatus.OPEN.value
            }
        )
        
        session.commit()
        
        return ReconciliationException(
            exception_id=exception_id,
            tenant_id=UUID(transaction['tenant_id']),
            transaction_id=UUID(transaction['transaction_id']),
            settlement_id=match.settlement_id if match else None,
            exception_type=exception_type,
            exception_reason=self._get_exception_reason(exception_type, match),
            amount_value=amount,
            amount_currency=transaction['amount_currency'],
            priority=priority,
            status=ExceptionStatus.OPEN
        )
    
    def _get_exception_reason(
        self,
        exception_type: ExceptionType,
        match: Optional[ReconciliationMatch]
    ) -> str:
        """Get human-readable exception reason"""
        reasons = {
            ExceptionType.UNMATCHED: "No matching settlement found",
            ExceptionType.PARTIAL_MATCH: "Fuzzy match requires manual review",
            ExceptionType.AMOUNT_MISMATCH: f"Amount difference: {match.amount_difference_percent}%" if match else "Amount mismatch",
            ExceptionType.DUPLICATE: "Duplicate transaction detected",
            ExceptionType.TIMING_MISMATCH: "Transaction date mismatch"
        }
        return reasons.get(exception_type, "Unknown exception")
    
    def _get_transaction(self, session, transaction_id: UUID) -> Optional[dict]:
        """Get transaction from database"""
        result = session.execute(
            text("""
                SELECT 
                    transaction_id, tenant_id, brand_id, entity_id,
                    psp_connection_id, event_type, event_timestamp, transaction_date,
                    amount_value, amount_currency,
                    psp_transaction_id, psp_payment_id, psp_settlement_id, psp_batch_id,
                    customer_id, player_id,
                    reconciliation_status
                FROM normalized_transaction
                WHERE transaction_id = :transaction_id
            """),
            {'transaction_id': str(transaction_id)}
        ).fetchone()
        
        if result:
            return {
                'transaction_id': UUID(result[0]),
                'tenant_id': UUID(result[1]),
                'brand_id': UUID(result[2]),
                'entity_id': UUID(result[3]),
                'psp_connection_id': result[4],
                'event_type': result[5],
                'event_timestamp': result[6],
                'transaction_date': result[7],
                'amount_value': result[8],
                'amount_currency': result[9],
                'psp_transaction_id': result[10],
                'psp_payment_id': result[11],
                'psp_settlement_id': result[12],
                'psp_batch_id': result[13],
                'customer_id': result[14],
                'player_id': result[15],
                'reconciliation_status': result[16]
            }
        return None

