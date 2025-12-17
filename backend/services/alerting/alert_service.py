"""
Alert Service - Sends alerts via PagerDuty, Slack, Email
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

import boto3

logger = logging.getLogger(__name__)

sns_client = boto3.client('sns')
ses_client = boto3.client('ses')


class AlertService:
    """Sends alerts and notifications"""
    
    def __init__(
        self,
        pagerduty_integration_key: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        sns_topic_arn: Optional[str] = None
    ):
        self.pagerduty_key = pagerduty_integration_key
        self.slack_webhook = slack_webhook_url
        self.sns_topic = sns_topic_arn
    
    async def send_alert(
        self,
        alert: Dict,
        tenant_id: Optional[UUID] = None
    ):
        """
        Send alert via appropriate channel based on priority
        
        P1 (Critical): PagerDuty → On-call engineer
        P2 (High): PagerDuty → On-call engineer (within 1 hour)
        P3 (Medium): Slack → Finance team
        P4 (Low): Email → Finance team (daily digest)
        """
        priority = alert.get('level', 'P3')
        
        if priority in ['P1', 'P2']:
            await self._send_pagerduty(alert, tenant_id)
        
        if priority in ['P2', 'P3']:
            await self._send_slack(alert, tenant_id)
        
        if priority == 'P4':
            await self._send_email(alert, tenant_id)
        
        # Also send to SNS for fan-out
        if self.sns_topic:
            await self._send_sns(alert, tenant_id)
    
    async def _send_pagerduty(self, alert: Dict, tenant_id: Optional[UUID]):
        """Send alert to PagerDuty"""
        if not self.pagerduty_key:
            logger.warning("PagerDuty integration key not configured")
            return
        
        # PagerDuty Events API v2
        import requests
        
        severity = 'critical' if alert.get('level') == 'P1' else 'error'
        
        payload = {
            'routing_key': self.pagerduty_key,
            'event_action': 'trigger',
            'payload': {
                'summary': alert.get('message', 'Reconciliation alert'),
                'severity': severity,
                'source': 'psp-reconciliation-platform',
                'custom_details': {
                    'alert_type': alert.get('type'),
                    'tenant_id': str(tenant_id) if tenant_id else None,
                    **alert
                }
            }
        }
        
        try:
            response = requests.post(
                'https://events.pagerduty.com/v2/enqueue',
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error sending PagerDuty alert: {str(e)}")
    
    async def _send_slack(self, alert: Dict, tenant_id: Optional[UUID]):
        """Send alert to Slack"""
        if not self.slack_webhook:
            logger.warning("Slack webhook URL not configured")
            return
        
        import requests
        
        color = {
            'P1': 'danger',
            'P2': 'warning',
            'P3': 'good',
            'P4': '#808080'
        }.get(alert.get('level', 'P3'), 'good')
        
        payload = {
            'attachments': [{
                'color': color,
                'title': f"Reconciliation Alert: {alert.get('type', 'Unknown')}",
                'text': alert.get('message', ''),
                'fields': [
                    {'title': 'Priority', 'value': alert.get('level', 'P3'), 'short': True},
                    {'title': 'Tenant', 'value': str(tenant_id) if tenant_id else 'N/A', 'short': True}
                ],
                'ts': int(datetime.utcnow().timestamp())
            }]
        }
        
        try:
            response = requests.post(self.slack_webhook, json=payload)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error sending Slack alert: {str(e)}")
    
    async def _send_email(self, alert: Dict, tenant_id: Optional[UUID]):
        """Send alert via email (SES)"""
        # TODO: Implement email sending via SES
        pass
    
    async def _send_sns(self, alert: Dict, tenant_id: Optional[UUID]):
        """Send alert to SNS topic for fan-out"""
        if not self.sns_topic:
            return
        
        message = {
            'alert': alert,
            'tenant_id': str(tenant_id) if tenant_id else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            sns_client.publish(
                TopicArn=self.sns_topic,
                Message=json.dumps(message),
                Subject=f"Reconciliation Alert: {alert.get('type', 'Unknown')}"
            )
        except Exception as e:
            logger.error(f"Error sending SNS alert: {str(e)}")

