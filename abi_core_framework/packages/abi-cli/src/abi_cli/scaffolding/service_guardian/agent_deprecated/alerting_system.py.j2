"""
Advanced Alerting System for Guardial Agent

This module implements comprehensive alerting capabilities including
email notifications, webhook integrations, and escalation policies.
"""

import json
import logging
import asyncio
import smtplib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from email.mime.text import MIMEText as MimeText
from email.mime.multipart import MIMEMultipart as MimeMultipart
from pathlib import Path
import os

logger = logging.getLogger(__name__)

# HTTP client imports with fallbacks
try:
    import aiohttp
    HTTP_CLIENT = 'aiohttp'
except ImportError:
    try:
        import httpx
        HTTP_CLIENT = 'httpx'
    except ImportError:
        # No HTTP client available - use mock for testing
        HTTP_CLIENT = 'mock'
        logger.warning("No HTTP client available (aiohttp/httpx), webhook alerts will be mocked")

from agent.metrics_collector import get_metrics_collector

@dataclass
class AlertChannel:
    """Alert delivery channel configuration"""
    name: str
    channel_type: str  # email, webhook, slack, teams
    config: Dict[str, Any]
    enabled: bool = True
    severity_filter: List[str] = field(default_factory=lambda: ["info", "warning", "error", "critical"])

@dataclass
class EscalationRule:
    """Alert escalation rule"""
    name: str
    condition: str  # "duration", "count", "severity"
    threshold: Any  # duration in seconds, count number, or severity level
    action: str  # "escalate", "notify_additional", "emergency_shutdown"
    target_channels: List[str]
    enabled: bool = True

@dataclass
class AlertTemplate:
    """Alert message template"""
    name: str
    subject_template: str
    body_template: str
    html_template: Optional[str] = None

class AlertingSystem:
    """Comprehensive alerting and notification system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "alerting_config.json"
        self.channels: Dict[str, AlertChannel] = {}
        self.escalation_rules: List[EscalationRule] = []
        self.templates: Dict[str, AlertTemplate] = {}
        self.alert_history: List[Dict[str, Any]] = []
        self.escalation_state: Dict[str, Dict[str, Any]] = {}
        
        # Load configuration
        self._load_configuration()
        
        # Setup default templates
        self._setup_default_templates()
        
        # Background task will be started when needed
        self._escalation_task = None
        
        logger.info("🔔 Alerting system initialized")
    
    def _load_configuration(self):
        """Load alerting configuration from file"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Load channels
                for channel_config in config.get("channels", []):
                    channel = AlertChannel(**channel_config)
                    self.channels[channel.name] = channel
                
                # Load escalation rules
                for rule_config in config.get("escalation_rules", []):
                    rule = EscalationRule(**rule_config)
                    self.escalation_rules.append(rule)
                
                logger.info(f"Loaded alerting configuration: {len(self.channels)} channels, {len(self.escalation_rules)} rules")
            else:
                logger.info("No alerting configuration found, using defaults")
                self._create_default_configuration()
        
        except Exception as e:
            logger.error(f"Failed to load alerting configuration: {e}")
            self._create_default_configuration()
    
    def _create_default_configuration(self):
        """Create default alerting configuration"""
        # Default email channel (if configured)
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        alert_email = os.getenv("ALERT_EMAIL")
        
        if all([smtp_server, smtp_user, smtp_password, alert_email]):
            email_channel = AlertChannel(
                name="default_email",
                channel_type="email",
                config={
                    "smtp_server": smtp_server,
                    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                    "smtp_user": smtp_user,
                    "smtp_password": smtp_password,
                    "from_email": smtp_user,
                    "to_emails": [alert_email],
                    "use_tls": True
                },
                severity_filter=["warning", "error", "critical"]
            )
            self.channels["default_email"] = email_channel
        
        # Default webhook channel (if configured)
        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if webhook_url:
            webhook_channel = AlertChannel(
                name="default_webhook",
                channel_type="webhook",
                config={
                    "url": webhook_url,
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "timeout": 30
                },
                severity_filter=["error", "critical"]
            )
            self.channels["default_webhook"] = webhook_channel
        
        # Default escalation rules
        self.escalation_rules = [
            EscalationRule(
                name="critical_immediate",
                condition="severity",
                threshold="critical",
                action="notify_additional",
                target_channels=list(self.channels.keys())
            ),
            EscalationRule(
                name="error_duration",
                condition="duration",
                threshold=300,  # 5 minutes
                action="escalate",
                target_channels=list(self.channels.keys())
            )
        ]
    
    def _setup_default_templates(self):
        """Setup default alert message templates"""
        self.templates["security_alert"] = AlertTemplate(
            name="security_alert",
            subject_template="🚨 Guardial Security Alert: {alert_type}",
            body_template="""
Security Alert Details:
- Alert Type: {alert_type}
- Severity: {severity}
- Message: {message}
- Timestamp: {timestamp}
- Metric: {metric_name} = {current_value}
- Threshold: {threshold}
- Duration: {duration_seconds} seconds

System Status: {system_status}

This alert was generated by the Guardial Security System.
""",
            html_template="""
<html>
<body>
<h2 style="color: #dc3545;">🚨 Guardial Security Alert</h2>
<table style="border-collapse: collapse; width: 100%;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Alert Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert_type}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Severity:</strong></td><td style="padding: 8px; border: 1px solid #ddd;"><span style="color: {severity_color};">{severity}</span></td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Message:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{message}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Metric:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{metric_name} = {current_value}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Threshold:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{threshold}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Duration:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{duration_seconds} seconds</td></tr>
</table>
<p><strong>System Status:</strong> {system_status}</p>
<p><em>This alert was generated by the Guardial Security System.</em></p>
</body>
</html>
"""
        )
        
        self.templates["emergency_alert"] = AlertTemplate(
            name="emergency_alert",
            subject_template="🚨 EMERGENCY: Guardial System Alert",
            body_template="""
EMERGENCY SYSTEM ALERT

Emergency Type: {emergency_type}
Emergency Level: {emergency_level}
Reason: {reason}
Initiated By: {initiated_by}
Timestamp: {timestamp}

IMMEDIATE ACTION REQUIRED

This is an automated emergency alert from the Guardial Security System.
""",
            html_template="""
<html>
<body style="background-color: #f8d7da; padding: 20px;">
<h1 style="color: #721c24; text-align: center;">🚨 EMERGENCY SYSTEM ALERT 🚨</h1>
<div style="background-color: white; padding: 20px; border: 3px solid #dc3545; border-radius: 5px;">
<table style="border-collapse: collapse; width: 100%;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Emergency Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: #dc3545;"><strong>{emergency_type}</strong></td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Emergency Level:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: #dc3545;"><strong>{emergency_level}</strong></td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Initiated By:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{initiated_by}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td></tr>
</table>
<h3 style="color: #dc3545; text-align: center;">IMMEDIATE ACTION REQUIRED</h3>
</div>
<p><em>This is an automated emergency alert from the Guardial Security System.</em></p>
</body>
</html>
"""
        )
    
    async def send_alert(self, alert_data: Dict[str, Any], template_name: str = "security_alert"):
        """Send alert through configured channels"""
        try:
            # Start escalation processing task if not already running
            if self._escalation_task is None or self._escalation_task.done():
                try:
                    self._escalation_task = asyncio.create_task(self._process_escalations())
                except RuntimeError:
                    # Event loop not running, skip background task for now
                    pass
            # Get template
            template = self.templates.get(template_name)
            if not template:
                logger.error(f"Alert template not found: {template_name}")
                return
            
            # Add severity color for HTML template
            severity_colors = {
                "info": "#17a2b8",
                "warning": "#ffc107", 
                "error": "#fd7e14",
                "critical": "#dc3545"
            }
            alert_data["severity_color"] = severity_colors.get(alert_data.get("severity", "info"), "#6c757d")
            
            # Format message
            subject = template.subject_template.format(**alert_data)
            body = template.body_template.format(**alert_data)
            html_body = template.html_template.format(**alert_data) if template.html_template else None
            
            # Get alert severity once for all channels
            alert_severity = alert_data.get("severity", "info")
            
            # Send through each channel
            for channel_name, channel in self.channels.items():
                if not channel.enabled:
                    continue
                
                # Check severity filter
                if alert_severity not in channel.severity_filter:
                    continue
                
                try:
                    if channel.channel_type == "email":
                        await self._send_email_alert(channel, subject, body, html_body, alert_data)
                    elif channel.channel_type == "webhook":
                        await self._send_webhook_alert(channel, alert_data, subject, body)
                    elif channel.channel_type == "slack":
                        await self._send_slack_alert(channel, alert_data, subject, body)
                    else:
                        logger.warning(f"Unsupported channel type: {channel.channel_type}")
                
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel_name}: {e}")
            
            # Record alert in history
            self.alert_history.append({
                **alert_data,
                "sent_at": datetime.utcnow().isoformat(),
                "template_used": template_name,
                "channels_sent": list(self.channels.keys())
            })
            
            # Check escalation rules
            await self._check_escalation_rules(alert_data)
            
            logger.info(f"Alert sent: {alert_data.get('alert_type', 'Unknown')} - {alert_severity}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    async def _send_email_alert(self, channel: AlertChannel, subject: str, body: str, html_body: Optional[str], alert_data: Dict[str, Any]):
        """Send alert via email"""
        try:
            config = channel.config
            
            # Create message
            msg = MimeMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = config['from_email']
            msg['To'] = ', '.join(config['to_emails'])
            
            # Add text part
            text_part = MimeText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if available
            if html_body:
                html_part = MimeText(html_body, 'html')
                msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                if config.get('use_tls', True):
                    server.starttls()
                server.login(config['smtp_user'], config['smtp_password'])
                server.send_message(msg)
            
            logger.info(f"Email alert sent to {len(config['to_emails'])} recipients")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            raise
    
    async def _send_webhook_alert(self, channel: AlertChannel, alert_data: Dict[str, Any], subject: str, body: str):
        """Send alert via webhook"""
        try:
            config = channel.config
            
            payload = {
                "alert_type": "guardial_security_alert",
                "subject": subject,
                "message": body,
                "alert_data": alert_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if HTTP_CLIENT == 'aiohttp':
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=config.get('method', 'POST'),
                        url=config['url'],
                        json=payload,
                        headers=config.get('headers', {}),
                        timeout=aiohttp.ClientTimeout(total=config.get('timeout', 30))
                    ) as response:
                        if response.status >= 400:
                            logger.error(f"Webhook alert failed with status {response.status}")
                            raise Exception(f"HTTP {response.status}")
            elif HTTP_CLIENT == 'httpx':
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=config.get('method', 'POST'),
                        url=config['url'],
                        json=payload,
                        headers=config.get('headers', {}),
                        timeout=config.get('timeout', 30)
                    )
                    if response.status_code >= 400:
                        logger.error(f"Webhook alert failed with status {response.status_code}")
                        raise Exception(f"HTTP {response.status_code}")
            else:
                # Mock mode for testing
                logger.info(f"Mock webhook alert sent to {config['url']}: {payload['subject']}")
            
            logger.info(f"Webhook alert sent to {config['url']}")
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            raise
    
    async def _send_slack_alert(self, channel: AlertChannel, alert_data: Dict[str, Any], subject: str, body: str):
        """Send alert via Slack webhook"""
        try:
            config = channel.config
            
            # Format Slack message
            severity = alert_data.get("severity", "info")
            color_map = {
                "info": "#36a64f",
                "warning": "#ff9500", 
                "error": "#ff4500",
                "critical": "#ff0000"
            }
            
            payload = {
                "text": subject,
                "attachments": [{
                    "color": color_map.get(severity, "#36a64f"),
                    "fields": [
                        {"title": "Severity", "value": severity.upper(), "short": True},
                        {"title": "Metric", "value": alert_data.get("metric_name", "N/A"), "short": True},
                        {"title": "Current Value", "value": str(alert_data.get("current_value", "N/A")), "short": True},
                        {"title": "Threshold", "value": str(alert_data.get("threshold", "N/A")), "short": True},
                        {"title": "Message", "value": alert_data.get("message", ""), "short": False}
                    ],
                    "footer": "Guardial Security System",
                    "ts": int(datetime.utcnow().timestamp())
                }]
            }
            
            if HTTP_CLIENT == 'aiohttp':
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        config['webhook_url'],
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=config.get('timeout', 30))
                    ) as response:
                        if response.status >= 400:
                            logger.error(f"Slack alert failed with status {response.status}")
                            raise Exception(f"HTTP {response.status}")
            elif HTTP_CLIENT == 'httpx':
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        config['webhook_url'],
                        json=payload,
                        timeout=config.get('timeout', 30)
                    )
                    if response.status_code >= 400:
                        logger.error(f"Slack alert failed with status {response.status_code}")
                        raise Exception(f"HTTP {response.status_code}")
            else:
                # Mock mode for testing
                logger.info(f"Mock Slack alert sent: {payload['text']}")
            
            logger.info("Slack alert sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            raise
    
    async def _check_escalation_rules(self, alert_data: Dict[str, Any]):
        """Check and apply escalation rules"""
        try:
            alert_key = f"{alert_data.get('metric_name', 'unknown')}_{alert_data.get('severity', 'info')}"
            
            for rule in self.escalation_rules:
                if not rule.enabled:
                    continue
                
                should_escalate = False
                
                if rule.condition == "severity":
                    # Escalate based on severity level
                    severity_levels = {"info": 1, "warning": 2, "error": 3, "critical": 4}
                    current_level = severity_levels.get(alert_data.get("severity", "info"), 1)
                    threshold_level = severity_levels.get(rule.threshold, 4)
                    should_escalate = current_level >= threshold_level
                
                elif rule.condition == "duration":
                    # Escalate based on alert duration
                    if alert_key not in self.escalation_state:
                        self.escalation_state[alert_key] = {
                            "first_seen": datetime.utcnow(),
                            "escalated": False
                        }
                    
                    state = self.escalation_state[alert_key]
                    duration = (datetime.utcnow() - state["first_seen"]).total_seconds()
                    should_escalate = duration >= rule.threshold and not state["escalated"]
                
                elif rule.condition == "count":
                    # Escalate based on alert count
                    if alert_key not in self.escalation_state:
                        self.escalation_state[alert_key] = {"count": 0, "escalated": False}
                    
                    state = self.escalation_state[alert_key]
                    state["count"] += 1
                    should_escalate = state["count"] >= rule.threshold and not state["escalated"]
                
                if should_escalate:
                    await self._execute_escalation_action(rule, alert_data, alert_key)
        
        except Exception as e:
            logger.error(f"Failed to check escalation rules: {e}")
    
    async def _execute_escalation_action(self, rule: EscalationRule, alert_data: Dict[str, Any], alert_key: str):
        """Execute escalation action"""
        try:
            if rule.action == "escalate":
                # Send escalated alert
                escalated_alert = {
                    **alert_data,
                    "alert_type": f"ESCALATED: {alert_data.get('alert_type', 'Alert')}",
                    "severity": "critical",
                    "escalation_rule": rule.name,
                    "escalated_at": datetime.utcnow().isoformat()
                }
                
                # Send only to target channels
                original_channels = self.channels.copy()
                self.channels = {name: channel for name, channel in self.channels.items() 
                               if name in rule.target_channels}
                
                await self.send_alert(escalated_alert, "security_alert")
                
                # Restore original channels
                self.channels = original_channels
                
                # Mark as escalated
                if alert_key in self.escalation_state:
                    self.escalation_state[alert_key]["escalated"] = True
                
                logger.warning(f"Alert escalated: {rule.name}")
            
            elif rule.action == "notify_additional":
                # Send to additional channels
                additional_alert = {
                    **alert_data,
                    "alert_type": f"HIGH PRIORITY: {alert_data.get('alert_type', 'Alert')}",
                    "escalation_rule": rule.name
                }
                
                # Send only to target channels
                original_channels = self.channels.copy()
                self.channels = {name: channel for name, channel in self.channels.items() 
                               if name in rule.target_channels}
                
                await self.send_alert(additional_alert, "security_alert")
                
                # Restore original channels
                self.channels = original_channels
                
                logger.info(f"Additional notifications sent: {rule.name}")
            
            elif rule.action == "emergency_shutdown":
                # Trigger emergency shutdown
                from agent.emergency_response import get_emergency_response_system, EmergencyType, EmergencyLevel
                
                emergency_system = get_emergency_response_system()
                await emergency_system.emergency_shutdown(
                    reason=f"Automatic escalation triggered by rule: {rule.name}",
                    initiated_by="ESCALATION_SYSTEM",
                    emergency_type=EmergencyType.AUTOMATIC_RESPONSE,
                    emergency_level=EmergencyLevel.CRITICAL
                )
                
                logger.critical(f"Emergency shutdown triggered by escalation rule: {rule.name}")
        
        except Exception as e:
            logger.error(f"Failed to execute escalation action: {e}")
    
    async def send_emergency_alert(self, emergency_data: Dict[str, Any]):
        """Send emergency alert with highest priority"""
        try:
            # Override channel filters for emergency alerts
            original_filters = {}
            for name, channel in self.channels.items():
                original_filters[name] = channel.severity_filter
                channel.severity_filter = ["info", "warning", "error", "critical"]  # Send to all
            
            # Send emergency alert
            await self.send_alert(emergency_data, "emergency_alert")
            
            # Restore original filters
            for name, channel in self.channels.items():
                channel.severity_filter = original_filters.get(name, ["info", "warning", "error", "critical"])
            
            logger.critical(f"Emergency alert sent: {emergency_data.get('emergency_type', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to send emergency alert: {e}")
    
    async def _process_escalations(self):
        """Background task to process escalations"""
        while True:
            try:
                # Clean up old escalation state
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                keys_to_remove = []
                for key, state in self.escalation_state.items():
                    if "first_seen" in state and state["first_seen"] < cutoff_time:
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    del self.escalation_state[key]
                
                await asyncio.sleep(300)  # Clean up every 5 minutes
                
            except Exception as e:
                logger.error(f"Escalation processing failed: {e}")
                await asyncio.sleep(600)
    
    def add_channel(self, channel: AlertChannel):
        """Add new alert channel"""
        self.channels[channel.name] = channel
        logger.info(f"Added alert channel: {channel.name} ({channel.channel_type})")
    
    def remove_channel(self, channel_name: str):
        """Remove alert channel"""
        if channel_name in self.channels:
            del self.channels[channel_name]
            logger.info(f"Removed alert channel: {channel_name}")
    
    def add_escalation_rule(self, rule: EscalationRule):
        """Add new escalation rule"""
        self.escalation_rules.append(rule)
        logger.info(f"Added escalation rule: {rule.name}")
    
    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history for specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["sent_at"]) >= cutoff_time
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Get alerting system status"""
        return {
            "channels": {name: {"type": ch.channel_type, "enabled": ch.enabled} 
                        for name, ch in self.channels.items()},
            "escalation_rules": len(self.escalation_rules),
            "active_escalations": len(self.escalation_state),
            "alerts_sent_24h": len(self.get_alert_history(24)),
            "templates": list(self.templates.keys())
        }


# Singleton instance
_alerting_system = None

def get_alerting_system() -> AlertingSystem:
    """Get singleton alerting system"""
    global _alerting_system
    if _alerting_system is None:
        _alerting_system = AlertingSystem()
    return _alerting_system