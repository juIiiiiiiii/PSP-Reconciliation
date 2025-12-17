"""
Chargeback Service - Manages chargeback lifecycle
"""

import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.models.chargeback import Chargeback, ChargebackStatus
from services.ledger.ledger_service import LedgerService

logger = logging.getLogger(__name__)


class ChargebackService:
    """Manages chargeback lifecycle and disputes"""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
        self.ledger_service = LedgerService(db_connection_string)
    
    async def create_chargeback(
        self,
        tenant_id: UUID,
        transaction_id: UUID,
        psp_chargeback_id: str,
        chargeback_amount: int,
        chargeback_currency: str,
        chargeback_date: date,
        chargeback_reason: Optional[str] = None,
        chargeback_reason_code: Optional[str] = None,
        dispute_deadline: Optional[date] = None
    ) -> Chargeback:
        """
        Create chargeback record from PSP webhook or manual entry
        
        Steps:
        1. Create chargeback record
        2. Match to original transaction
        3. Update transaction status
        4. Post to ledger (if auto-posting enabled)
        """
        with self.SessionLocal() as session:
            # Check if chargeback already exists
            existing = session.execute(
                text("""
                    SELECT chargeback_id
                    FROM chargeback
                    WHERE tenant_id = :tenant_id
                    AND psp_chargeback_id = :psp_chargeback_id
                """),
                {
                    'tenant_id': str(tenant_id),
                    'psp_chargeback_id': psp_chargeback_id
                }
            ).fetchone()
            
            if existing:
                logger.info(f"Chargeback already exists: {psp_chargeback_id}")
                return await self.get_chargeback(UUID(existing[0]))
            
            # Create chargeback
            chargeback_id = uuid4()
            
            session.execute(
                text("""
                    INSERT INTO chargeback (
                        chargeback_id, tenant_id, transaction_id,
                        psp_chargeback_id, chargeback_reason, chargeback_reason_code,
                        chargeback_amount, chargeback_currency, chargeback_date,
                        dispute_deadline, status
                    ) VALUES (
                        :chargeback_id, :tenant_id, :transaction_id,
                        :psp_chargeback_id, :chargeback_reason, :chargeback_reason_code,
                        :chargeback_amount, :chargeback_currency, :chargeback_date,
                        :dispute_deadline, :status
                    )
                """),
                {
                    'chargeback_id': str(chargeback_id),
                    'tenant_id': str(tenant_id),
                    'transaction_id': str(transaction_id),
                    'psp_chargeback_id': psp_chargeback_id,
                    'chargeback_reason': chargeback_reason,
                    'chargeback_reason_code': chargeback_reason_code,
                    'chargeback_amount': chargeback_amount,
                    'chargeback_currency': chargeback_currency,
                    'chargeback_date': chargeback_date,
                    'dispute_deadline': dispute_deadline,
                    'status': ChargebackStatus.INITIATED.value
                }
            )
            
            session.commit()
            
            return await self.get_chargeback(chargeback_id)
    
    async def get_chargeback(self, chargeback_id: UUID) -> Chargeback:
        """Get chargeback by ID"""
        with self.SessionLocal() as session:
            result = session.execute(
                text("""
                    SELECT 
                        chargeback_id, tenant_id, transaction_id,
                        psp_chargeback_id, chargeback_reason, chargeback_reason_code,
                        chargeback_amount, chargeback_currency, chargeback_date,
                        dispute_deadline, status, dispute_evidence,
                        assigned_to_user_id, resolved_at, resolved_by_user_id,
                        notes, created_at, updated_at
                    FROM chargeback
                    WHERE chargeback_id = :chargeback_id
                """),
                {'chargeback_id': str(chargeback_id)}
            ).fetchone()
            
            if not result:
                raise ValueError(f"Chargeback not found: {chargeback_id}")
            
            return Chargeback(
                chargeback_id=UUID(result[0]),
                tenant_id=UUID(result[1]),
                transaction_id=UUID(result[2]),
                psp_chargeback_id=result[3],
                chargeback_reason=result[4],
                chargeback_reason_code=result[5],
                chargeback_amount=result[6],
                chargeback_currency=result[7],
                chargeback_date=result[8],
                dispute_deadline=result[9],
                status=ChargebackStatus(result[10]),
                dispute_evidence=result[11] if result[11] else {},
                assigned_to_user_id=UUID(result[12]) if result[12] else None,
                resolved_at=result[13],
                resolved_by_user_id=UUID(result[14]) if result[14] else None,
                notes=result[15],
                created_at=result[16],
                updated_at=result[17]
            )
    
    async def update_chargeback_status(
        self,
        chargeback_id: UUID,
        new_status: ChargebackStatus,
        user_id: UUID,
        notes: Optional[str] = None,
        dispute_evidence: Optional[Dict[str, Any]] = None
    ) -> Chargeback:
        """
        Update chargeback status (workflow transitions)
        
        Valid transitions:
        - INITIATED -> UNDER_REVIEW
        - UNDER_REVIEW -> ACCEPTED or DISPUTED
        - DISPUTED -> WON or LOST
        - WON -> REVERSED
        """
        with self.SessionLocal() as session:
            # Get current chargeback
            chargeback = await self.get_chargeback(chargeback_id)
            
            # Validate transition
            if not self._is_valid_transition(chargeback.status, new_status):
                raise ValueError(
                    f"Invalid status transition: {chargeback.status} -> {new_status}"
                )
            
            # Update status
            update_fields = {
                'status': new_status.value,
                'updated_at': datetime.utcnow()
            }
            
            if new_status == ChargebackStatus.UNDER_REVIEW:
                update_fields['assigned_to_user_id'] = str(user_id)
            elif new_status in [ChargebackStatus.ACCEPTED, ChargebackStatus.LOST, ChargebackStatus.REVERSED]:
                update_fields['resolved_at'] = datetime.utcnow()
                update_fields['resolved_by_user_id'] = str(user_id)
            
            if notes:
                update_fields['notes'] = notes
            
            if dispute_evidence:
                update_fields['dispute_evidence'] = dispute_evidence
            
            # Build update query
            set_clause = ', '.join([f"{k} = :{k}" for k in update_fields.keys()])
            
            session.execute(
                text(f"""
                    UPDATE chargeback
                    SET {set_clause}
                    WHERE chargeback_id = :chargeback_id
                """),
                {**update_fields, 'chargeback_id': str(chargeback_id)}
            )
            
            session.commit()
            
            # If status is REVERSED, post reversal to ledger
            if new_status == ChargebackStatus.REVERSED:
                await self._post_chargeback_reversal(chargeback)
            
            return await self.get_chargeback(chargeback_id)
    
    def _is_valid_transition(
        self,
        current_status: ChargebackStatus,
        new_status: ChargebackStatus
    ) -> bool:
        """Validate status transition"""
        valid_transitions = {
            ChargebackStatus.INITIATED: [
                ChargebackStatus.UNDER_REVIEW
            ],
            ChargebackStatus.UNDER_REVIEW: [
                ChargebackStatus.ACCEPTED,
                ChargebackStatus.DISPUTED
            ],
            ChargebackStatus.DISPUTED: [
                ChargebackStatus.WON,
                ChargebackStatus.LOST
            ],
            ChargebackStatus.WON: [
                ChargebackStatus.REVERSED
            ],
            ChargebackStatus.ACCEPTED: [],  # Terminal
            ChargebackStatus.LOST: [],  # Terminal
            ChargebackStatus.REVERSED: []  # Terminal
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    async def _post_chargeback_reversal(self, chargeback: Chargeback):
        """Post chargeback reversal to ledger"""
        # This would create a reversal transaction and post to ledger
        # Similar to posting a chargeback but with opposite amounts
        pass
    
    async def list_chargebacks(
        self,
        tenant_id: UUID,
        status: Optional[ChargebackStatus] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Chargeback]:
        """List chargebacks with filters"""
        with self.SessionLocal() as session:
            query = """
                SELECT chargeback_id
                FROM chargeback
                WHERE tenant_id = :tenant_id
            """
            params = {'tenant_id': str(tenant_id)}
            
            if status:
                query += " AND status = :status"
                params['status'] = status.value
            
            if start_date:
                query += " AND chargeback_date >= :start_date"
                params['start_date'] = start_date
            
            if end_date:
                query += " AND chargeback_date <= :end_date"
                params['end_date'] = end_date
            
            query += " ORDER BY chargeback_date DESC"
            
            results = session.execute(text(query), params).fetchall()
            
            chargebacks = []
            for (chargeback_id,) in results:
                chargebacks.append(await self.get_chargeback(UUID(chargeback_id)))
            
            return chargebacks

