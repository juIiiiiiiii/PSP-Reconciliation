"""
Unit tests for rule engine
Target: 85% coverage
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from backend.services.reconciliation.rule_engine import RuleEngine


class TestRuleEngine:
    """Test rule engine"""
    
    @pytest.fixture
    def rule_engine(self):
        """Create rule engine instance"""
        return RuleEngine(
            db_connection_string="postgresql://test:test@localhost:5432/test"
        )
    
    def test_evaluate_conditions_and(self, rule_engine):
        """Test AND condition evaluation"""
        conditions = {
            'operator': 'and',
            'conditions': [
                {'field': 'amount_value', 'operator': 'gt', 'value': 10000},
                {'field': 'amount_value', 'operator': 'lt', 'value': 1000000}
            ]
        }
        context = {'amount_value': 50000}
        
        result = rule_engine._evaluate_conditions(conditions, context)
        assert result is True
        
        context = {'amount_value': 5000}
        result = rule_engine._evaluate_conditions(conditions, context)
        assert result is False
    
    def test_evaluate_conditions_or(self, rule_engine):
        """Test OR condition evaluation"""
        conditions = {
            'operator': 'or',
            'conditions': [
                {'field': 'amount_value', 'operator': 'lt', 'value': 10000},
                {'field': 'amount_value', 'operator': 'gt', 'value': 1000000}
            ]
        }
        context = {'amount_value': 5000}
        
        result = rule_engine._evaluate_conditions(conditions, context)
        assert result is True
    
    def test_evaluate_conditions_not(self, rule_engine):
        """Test NOT condition evaluation"""
        conditions = {
            'operator': 'not',
            'condition': {'field': 'amount_value', 'operator': 'lt', 'value': 10000}
        }
        context = {'amount_value': 50000}
        
        result = rule_engine._evaluate_conditions(conditions, context)
        assert result is True
    
    def test_evaluate_condition_operators(self, rule_engine):
        """Test various condition operators"""
        context = {'amount_value': 50000, 'currency': 'USD'}
        
        # eq
        assert rule_engine._evaluate_condition(
            {'field': 'amount_value', 'operator': 'eq', 'value': 50000}, context
        ) is True
        
        # ne
        assert rule_engine._evaluate_condition(
            {'field': 'amount_value', 'operator': 'ne', 'value': 10000}, context
        ) is True
        
        # gt
        assert rule_engine._evaluate_condition(
            {'field': 'amount_value', 'operator': 'gt', 'value': 10000}, context
        ) is True
        
        # gte
        assert rule_engine._evaluate_condition(
            {'field': 'amount_value', 'operator': 'gte', 'value': 50000}, context
        ) is True
        
        # lt
        assert rule_engine._evaluate_condition(
            {'field': 'amount_value', 'operator': 'lt', 'value': 100000}, context
        ) is True
        
        # lte
        assert rule_engine._evaluate_condition(
            {'field': 'amount_value', 'operator': 'lte', 'value': 50000}, context
        ) is True
        
        # in
        assert rule_engine._evaluate_condition(
            {'field': 'currency', 'operator': 'in', 'value': ['USD', 'EUR']}, context
        ) is True
        
        # contains
        assert rule_engine._evaluate_condition(
            {'field': 'currency', 'operator': 'contains', 'value': 'US'}, context
        ) is True
    
    def test_get_nested_value(self, rule_engine):
        """Test getting nested values from context"""
        context = {
            'transaction': {
                'amount': {
                    'value': 50000
                }
            }
        }
        
        value = rule_engine._get_nested_value(context, 'transaction.amount.value')
        assert value == 50000
        
        value = rule_engine._get_nested_value(context, 'transaction.amount.currency')
        assert value is None


