"""
Rule Engine - Tenant-configurable reconciliation rules
"""

import json
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class RuleEngine:
    """Evaluates tenant-configurable reconciliation rules"""
    
    def __init__(self, db_connection_string: str):
        self.db_engine = create_engine(db_connection_string)
        self.SessionLocal = sessionmaker(bind=self.db_engine)
    
    async def evaluate_rules(
        self,
        tenant_id: UUID,
        rule_type: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate rules for a given context
        
        Args:
            tenant_id: Tenant ID
            rule_type: MATCHING, EXCEPTION, or ALERT
            context: Context data (transaction, settlement, match, etc.)
        
        Returns:
            List of actions to execute (in priority order)
        """
        with self.SessionLocal() as session:
            # Get enabled rules for tenant, ordered by priority
            rules = session.execute(
                text("""
                    SELECT rule_id, rule_name, conditions, actions, priority
                    FROM reconciliation_rule
                    WHERE tenant_id = :tenant_id
                    AND rule_type = :rule_type
                    AND enabled = true
                    ORDER BY priority ASC
                """),
                {
                    'tenant_id': str(tenant_id),
                    'rule_type': rule_type
                }
            ).fetchall()
            
            matched_actions = []
            
            for rule in rules:
                rule_id, rule_name, conditions, actions, priority = rule
                
                # Evaluate conditions
                if self._evaluate_conditions(conditions, context):
                    logger.info(f"Rule matched: {rule_name} (priority: {priority})")
                    matched_actions.append({
                        'rule_id': str(rule_id),
                        'rule_name': rule_name,
                        'actions': json.loads(actions) if isinstance(actions, str) else actions,
                        'priority': priority
                    })
            
            return matched_actions
    
    def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate rule conditions against context
        
        Supports:
        - Field comparisons (eq, ne, gt, gte, lt, lte, in, contains)
        - Logical operators (and, or, not)
        - Nested conditions
        """
        if not conditions:
            return True
        
        operator = conditions.get('operator', 'and')
        
        if operator == 'and':
            return all(
                self._evaluate_condition(cond, context)
                for cond in conditions.get('conditions', [])
            )
        elif operator == 'or':
            return any(
                self._evaluate_condition(cond, context)
                for cond in conditions.get('conditions', [])
            )
        elif operator == 'not':
            return not self._evaluate_condition(
                conditions.get('condition'), context
            )
        else:
            # Single condition
            return self._evaluate_condition(conditions, context)
    
    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate a single condition"""
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')
        
        # Get field value from context (supports dot notation)
        field_value = self._get_nested_value(context, field)
        
        if operator == 'eq':
            return field_value == value
        elif operator == 'ne':
            return field_value != value
        elif operator == 'gt':
            return field_value > value
        elif operator == 'gte':
            return field_value >= value
        elif operator == 'lt':
            return field_value < value
        elif operator == 'lte':
            return field_value <= value
        elif operator == 'in':
            return field_value in value
        elif operator == 'contains':
            return value in str(field_value)
        elif operator == 'regex':
            import re
            return bool(re.match(value, str(field_value)))
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
    
    def _get_nested_value(self, obj: Dict, path: str) -> Any:
        """Get nested value from dict using dot notation"""
        keys = path.split('.')
        value = obj
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    async def execute_actions(
        self,
        actions: List[Dict[str, Any]],
        context: Dict[str, Any]
    ):
        """
        Execute rule actions
        
        Supported actions:
        - auto_match: Automatically create match
        - create_exception: Create exception with specific priority
        - send_alert: Send alert
        - skip_matching: Skip normal matching process
        - set_status: Set reconciliation status
        """
        for action_group in actions:
            for action in action_group.get('actions', []):
                action_type = action.get('type')
                
                if action_type == 'auto_match':
                    await self._execute_auto_match(action, context)
                elif action_type == 'create_exception':
                    await self._execute_create_exception(action, context)
                elif action_type == 'send_alert':
                    await self._execute_send_alert(action, context)
                elif action_type == 'skip_matching':
                    context['skip_matching'] = True
                elif action_type == 'set_status':
                    await self._execute_set_status(action, context)
    
    async def _execute_auto_match(self, action: Dict, context: Dict):
        """Execute auto-match action"""
        # This would create a match directly
        # Integration with matching engine
        pass
    
    async def _execute_create_exception(self, action: Dict, context: Dict):
        """Execute create exception action"""
        # This would create an exception with specified priority
        # Integration with exception service
        pass
    
    async def _execute_send_alert(self, action: Dict, context: Dict):
        """Execute send alert action"""
        # Integration with alert service
        pass
    
    async def _execute_set_status(self, action: Dict, context: Dict):
        """Execute set status action"""
        # Update transaction status
        pass


