"""
Ledger Service - Double-entry accounting
Posts matched transactions to ledger with double-entry bookkeeping
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.models.ledger import LedgerEntry

logger = logging.getLogger(__name__)


class ChartOfAccounts:
    """Chart of accounts mapping"""
    
    # Assets
    CASH_STRIPE_USD = "1001"
    CASH_ADYEN_EUR = "1002"
    CASH_PAYPAL_GBP = "1003"
    ACCOUNTS_RECEIVABLE = "1100"
    RESERVES_ROLLING = "1200"
    
    # Liabilities
    PLAYER_BALANCES = "2000"
    
    # Revenue
    GAMING_REVENUE = "4000"
    FX_GAINS = "4100"
    
    # Expenses
    PSP_FEES = "5000"
    FX_LOSSES = "5100"
    CHARGEBACK_LOSSES = "5200"
    
    @classmethod
    def get_cash_account(cls, psp_connection_id: str, currency: str) -> str:
        """Get cash account code for PSP and currency"""
        # Map PSP to account code
        psp_mapping = {
            'stripe': cls.CASH_STRIPE_USD,
            'adyen': cls.CASH_ADYEN_EUR,
            'paypal': cls.CASH_PAYPAL_GBP,
        }
        
        # Extract PSP name from connection ID
        psp_name = psp_connection_id.split('_')[0].lower()
        base_account = psp_mapping.get(psp_name, cls.CASH_STRIPE_USD)
        
        # For now, return base account (currency-specific accounts would be added)
        return base_account


class LedgerService:
    """Double-entry ledger service"""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
        self.chart = ChartOfAccounts()
    
    async def post_matched_transaction(
        self,
        transaction_id: UUID,
        match_id: UUID
    ) -> List[LedgerEntry]:
        """
        Post matched transaction to ledger with double-entry accounting
        
        Example: Deposit $1000 with $29.50 fee
        Debit: Cash (Stripe USD) $971.00
        Debit: PSP Fees $29.50
        Credit: Accounts Receivable $1000.00
        """
        with self.SessionLocal() as session:
            # Get transaction and match
            transaction = self._get_transaction(session, transaction_id)
            match = self._get_match(session, match_id)
            
            if not transaction or not match:
                raise ValueError("Transaction or match not found")
            
            # Generate ledger entries based on event type
            event_type = transaction['event_type']
            
            if event_type == 'DEPOSIT':
                entries = await self._post_deposit(session, transaction, match)
            elif event_type == 'WITHDRAWAL':
                entries = await self._post_withdrawal(session, transaction, match)
            elif event_type == 'REFUND':
                entries = await self._post_refund(session, transaction, match)
            elif event_type == 'CHARGEBACK':
                entries = await self._post_chargeback(session, transaction, match)
            elif event_type == 'FEE':
                entries = await self._post_fee(session, transaction, match)
            else:
                raise ValueError(f"Unsupported event type for ledger posting: {event_type}")
            
            # Update transaction status
            session.execute(
                text("""
                    UPDATE normalized_transaction
                    SET reconciliation_status = 'POSTED'
                    WHERE transaction_id = :transaction_id
                """),
                {'transaction_id': str(transaction_id)}
            )
            
            session.commit()
            
            return entries
    
    async def _post_deposit(
        self,
        session,
        transaction: dict,
        match: dict
    ) -> List[LedgerEntry]:
        """Post deposit transaction"""
        entries = []
        
        amount = transaction['amount_value']
        currency = transaction['amount_currency']
        psp_fee = transaction.get('psp_fee', 0)
        net_amount = transaction.get('net_amount', amount - psp_fee)
        
        # Get cash account
        cash_account = self.chart.get_cash_account(
            transaction['psp_connection_id'], currency
        )
        
        # Entry 1: Debit Cash, Credit Accounts Receivable
        entry1 = await self._create_entry(
            session,
            transaction['tenant_id'],
            transaction['entity_id'],
            transaction['transaction_date'],
            cash_account,
            self.chart.ACCOUNTS_RECEIVABLE,
            net_amount,
            currency,
            transaction['transaction_id'],
            match['match_id'],
            f"Deposit: {transaction['psp_transaction_id']}"
        )
        entries.append(entry1)
        
        # Entry 2: Debit PSP Fees, Credit Cash (if fee > 0)
        if psp_fee > 0:
            entry2 = await self._create_entry(
                session,
                transaction['tenant_id'],
                transaction['entity_id'],
                transaction['transaction_date'],
                self.chart.PSP_FEES,
                cash_account,
                psp_fee,
                currency,
                transaction['transaction_id'],
                match['match_id'],
                f"PSP Fee: {transaction['psp_transaction_id']}"
            )
            entries.append(entry2)
        
        return entries
    
    async def _post_withdrawal(
        self,
        session,
        transaction: dict,
        match: dict
    ) -> List[LedgerEntry]:
        """Post withdrawal transaction"""
        entries = []
        
        amount = transaction['amount_value']
        currency = transaction['amount_currency']
        cash_account = self.chart.get_cash_account(
            transaction['psp_connection_id'], currency
        )
        
        # Debit Player Balances, Credit Cash
        entry = await self._create_entry(
            session,
            transaction['tenant_id'],
            transaction['entity_id'],
            transaction['transaction_date'],
            self.chart.PLAYER_BALANCES,
            cash_account,
            amount,
            currency,
            transaction['transaction_id'],
            match['match_id'],
            f"Withdrawal: {transaction['psp_transaction_id']}"
        )
        entries.append(entry)
        
        return entries
    
    async def _post_refund(
        self,
        session,
        transaction: dict,
        match: dict
    ) -> List[LedgerEntry]:
        """Post refund transaction"""
        entries = []
        
        amount = transaction['amount_value']
        currency = transaction['amount_currency']
        cash_account = self.chart.get_cash_account(
            transaction['psp_connection_id'], currency
        )
        
        # Debit Accounts Receivable, Credit Cash
        entry = await self._create_entry(
            session,
            transaction['tenant_id'],
            transaction['entity_id'],
            transaction['transaction_date'],
            self.chart.ACCOUNTS_RECEIVABLE,
            cash_account,
            amount,
            currency,
            transaction['transaction_id'],
            match['match_id'],
            f"Refund: {transaction['psp_transaction_id']}"
        )
        entries.append(entry)
        
        return entries
    
    async def _post_chargeback(
        self,
        session,
        transaction: dict,
        match: dict
    ) -> List[LedgerEntry]:
        """Post chargeback transaction"""
        entries = []
        
        amount = transaction['amount_value']
        currency = transaction['amount_currency']
        cash_account = self.chart.get_cash_account(
            transaction['psp_connection_id'], currency
        )
        
        # Entry 1: Debit Chargeback Losses, Credit Cash
        entry1 = await self._create_entry(
            session,
            transaction['tenant_id'],
            transaction['entity_id'],
            transaction['transaction_date'],
            self.chart.CHARGEBACK_LOSSES,
            cash_account,
            amount,
            currency,
            transaction['transaction_id'],
            match['match_id'],
            f"Chargeback: {transaction['psp_transaction_id']}"
        )
        entries.append(entry1)
        
        # Entry 2: Debit Accounts Receivable (reversal), Credit Accounts Receivable
        # (This reverses the original deposit)
        entry2 = await self._create_entry(
            session,
            transaction['tenant_id'],
            transaction['entity_id'],
            transaction['transaction_date'],
            self.chart.ACCOUNTS_RECEIVABLE,
            self.chart.ACCOUNTS_RECEIVABLE,  # Self-reversal
            amount,
            currency,
            transaction['transaction_id'],
            match['match_id'],
            f"Chargeback Reversal: {transaction['psp_transaction_id']}"
        )
        entries.append(entry2)
        
        return entries
    
    async def _post_fee(
        self,
        session,
        transaction: dict,
        match: dict
    ) -> List[LedgerEntry]:
        """Post fee transaction"""
        entries = []
        
        amount = transaction['amount_value']
        currency = transaction['amount_currency']
        cash_account = self.chart.get_cash_account(
            transaction['psp_connection_id'], currency
        )
        
        # Debit PSP Fees, Credit Cash
        entry = await self._create_entry(
            session,
            transaction['tenant_id'],
            transaction['entity_id'],
            transaction['transaction_date'],
            self.chart.PSP_FEES,
            cash_account,
            amount,
            currency,
            transaction['transaction_id'],
            match['match_id'],
            f"Fee: {transaction['psp_transaction_id']}"
        )
        entries.append(entry)
        
        return entries
    
    async def _create_entry(
        self,
        session,
        tenant_id: UUID,
        entity_id: UUID,
        transaction_date: date,
        account_debit: str,
        account_credit: str,
        amount: int,
        currency: str,
        reference_transaction_id: UUID,
        reference_match_id: UUID,
        description: str
    ) -> LedgerEntry:
        """Create ledger entry"""
        entry_id = uuid4()
        
        session.execute(
            text("""
                INSERT INTO ledger_entry (
                    ledger_entry_id, tenant_id, entity_id, transaction_date,
                    account_debit, account_credit, amount, currency,
                    reference_transaction_id, reference_match_id,
                    description, posted_at, posted_by_system
                ) VALUES (
                    :entry_id, :tenant_id, :entity_id, :transaction_date,
                    :account_debit, :account_credit, :amount, :currency,
                    :reference_transaction_id, :reference_match_id,
                    :description, NOW(), true
                )
            """),
            {
                'entry_id': str(entry_id),
                'tenant_id': str(tenant_id),
                'entity_id': str(entity_id),
                'transaction_date': transaction_date,
                'account_debit': account_debit,
                'account_credit': account_credit,
                'amount': amount,
                'currency': currency,
                'reference_transaction_id': str(reference_transaction_id),
                'reference_match_id': str(reference_match_id),
                'description': description
            }
        )
        
        return LedgerEntry(
            ledger_entry_id=entry_id,
            tenant_id=tenant_id,
            entity_id=entity_id,
            transaction_date=transaction_date,
            account_debit=account_debit,
            account_credit=account_credit,
            amount=amount,
            currency=currency,
            reference_transaction_id=reference_transaction_id,
            reference_match_id=reference_match_id,
            description=description,
            posted_at=datetime.utcnow(),
            posted_by_system=True
        )
    
    def _get_transaction(self, session, transaction_id: UUID) -> Optional[dict]:
        """Get transaction from database"""
        result = session.execute(
            text("""
                SELECT 
                    transaction_id, tenant_id, entity_id,
                    psp_connection_id, event_type, transaction_date,
                    amount_value, amount_currency, psp_fee, net_amount,
                    psp_transaction_id
                FROM normalized_transaction
                WHERE transaction_id = :transaction_id
            """),
            {'transaction_id': str(transaction_id)}
        ).fetchone()
        
        if result:
            return {
                'transaction_id': UUID(result[0]),
                'tenant_id': UUID(result[1]),
                'entity_id': UUID(result[2]),
                'psp_connection_id': result[3],
                'event_type': result[4],
                'transaction_date': result[5],
                'amount_value': result[6],
                'amount_currency': result[7],
                'psp_fee': result[8],
                'net_amount': result[9],
                'psp_transaction_id': result[10]
            }
        return None
    
    def _get_match(self, session, match_id: UUID) -> Optional[dict]:
        """Get match from database"""
        result = session.execute(
            text("""
                SELECT match_id, transaction_id, settlement_id
                FROM reconciliation_match
                WHERE match_id = :match_id
            """),
            {'match_id': str(match_id)}
        ).fetchone()
        
        if result:
            return {
                'match_id': UUID(result[0]),
                'transaction_id': UUID(result[1]),
                'settlement_id': UUID(result[2]) if result[2] else None
            }
        return None


