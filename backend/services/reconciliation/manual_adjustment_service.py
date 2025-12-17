"""
Manual Adjustment Service - Handles manual corrections and approvals
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.models.user import User, UserRole

logger = logging.getLogger(__name__)


class ManualAdjustmentService:
    """Manages manual adjustments with approval workflows"""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
    
    async def create_adjustment(
        self,
        tenant_id: UUID,
        exception_id: Optional[UUID],
        adjustment_type: str,
        amount_value: int,
        amount_currency: str,
        description: str,
        created_by_user: User,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create manual adjustment
        
        Approval requirements:
        - < $10k: Finance Manager approval
        - >= $10k: Finance Director approval
        """
        adjustment_id = uuid4()
        
        # Determine if approval required
        approval_required = amount_value >= 1000000  # >= $10k
        
        with self.SessionLocal() as session:
            session.execute(
                text("""
                    INSERT INTO manual_adjustment (
                        adjustment_id, tenant_id, exception_id,
                        adjustment_type, amount_value, amount_currency,
                        description, created_by_user_id,
                        approval_status, approval_required,
                        metadata
                    ) VALUES (
                        :adjustment_id, :tenant_id, :exception_id,
                        :adjustment_type, :amount_value, :amount_currency,
                        :description, :created_by_user_id,
                        'PENDING', :approval_required,
                        :metadata
                    )
                """),
                {
                    'adjustment_id': str(adjustment_id),
                    'tenant_id': str(tenant_id),
                    'exception_id': str(exception_id) if exception_id else None,
                    'adjustment_type': adjustment_type,
                    'amount_value': amount_value,
                    'amount_currency': amount_currency,
                    'description': description,
                    'created_by_user_id': str(created_by_user.user_id),
                    'approval_required': approval_required,
                    'metadata': json.dumps(metadata) if metadata else None
                }
            )
            
            session.commit()
        
        return {
            'adjustment_id': str(adjustment_id),
            'approval_required': approval_required,
            'approval_status': 'PENDING'
        }
    
    async def approve_adjustment(
        self,
        adjustment_id: UUID,
        approved_by_user: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve manual adjustment
        
        Validates:
        - User has permission to approve (based on amount)
        - Adjustment is in PENDING status
        - Four-eyes principle (if required)
        """
        with self.SessionLocal() as session:
            # Get adjustment
            adjustment = session.execute(
                text("""
                    SELECT 
                        adjustment_id, tenant_id, amount_value,
                        approval_status, approval_required,
                        created_by_user_id
                    FROM manual_adjustment
                    WHERE adjustment_id = :adjustment_id
                """),
                {'adjustment_id': str(adjustment_id)}
            ).fetchone()
            
            if not adjustment:
                raise ValueError(f"Adjustment not found: {adjustment_id}")
            
            if adjustment[3] != 'PENDING':  # approval_status
                raise ValueError(f"Adjustment already {adjustment[3]}")
            
            # Check permission
            amount = adjustment[2]
            if amount >= 1000000:  # >= $10k
                if approved_by_user.role not in [UserRole.FINANCE_DIRECTOR, UserRole.TENANT_ADMIN, UserRole.PLATFORM_ADMIN]:
                    raise PermissionError("Finance Director approval required for adjustments >= $10k")
            else:
                if approved_by_user.role not in [UserRole.FINANCE_MANAGER, UserRole.FINANCE_DIRECTOR, UserRole.TENANT_ADMIN, UserRole.PLATFORM_ADMIN]:
                    raise PermissionError("Finance Manager approval required for adjustments < $10k")
            
            # Check four-eyes principle (creator cannot approve)
            if UUID(adjustment[5]) == approved_by_user.user_id:
                raise ValueError("Creator cannot approve their own adjustment (four-eyes principle)")
            
            # Approve
            session.execute(
                text("""
                    UPDATE manual_adjustment
                    SET approval_status = 'APPROVED',
                        approved_by_user_id = :approved_by_user_id,
                        approved_at = NOW()
                    WHERE adjustment_id = :adjustment_id
                """),
                {
                    'adjustment_id': str(adjustment_id),
                    'approved_by_user_id': str(approved_by_user.user_id)
                }
            )
            
            session.commit()
            
            # Post to ledger if adjustment type requires it
            if adjustment[1] == 'MANUAL_MATCH':  # adjustment_type
                await self._post_adjustment_to_ledger(adjustment_id)
            
            return {
                'adjustment_id': str(adjustment_id),
                'approval_status': 'APPROVED',
                'approved_by': str(approved_by_user.user_id)
            }
    
    async def reject_adjustment(
        self,
        adjustment_id: UUID,
        rejected_by_user: User,
        reason: str
    ):
        """Reject manual adjustment"""
        with self.SessionLocal() as session:
            session.execute(
                text("""
                    UPDATE manual_adjustment
                    SET approval_status = 'REJECTED',
                        approved_by_user_id = :rejected_by_user_id,
                        approved_at = NOW(),
                        metadata = jsonb_set(
                            COALESCE(metadata, '{}'::jsonb),
                            '{rejection_reason}',
                            :reason::jsonb
                        )
                    WHERE adjustment_id = :adjustment_id
                """),
                {
                    'adjustment_id': str(adjustment_id),
                    'rejected_by_user_id': str(rejected_by_user.user_id),
                    'reason': json.dumps(reason)
                }
            )
            session.commit()
    
    async def _post_adjustment_to_ledger(self, adjustment_id: UUID):
        """Post approved adjustment to ledger"""
        # Integration with ledger service
        pass

