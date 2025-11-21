# Guardial Security Dashboard and Alerting System

## Overview

The Guardial Security Dashboard and Alerting System provides comprehensive real-time monitoring, visualization, and automated alerting capabilities for the ABI security infrastructure. This implementation fulfills Task 5.4 requirements for monitoring dashboards and alerting.

## Features

### 🖥️ Real-time Security Dashboard

- **Live Metrics Display**: Real-time visualization of key security metrics
- **Interactive Charts**: Decision distribution, risk assessment, and performance trends
- **System Health Monitoring**: Component status indicators and health checks
- **Responsive Web Interface**: Modern Bootstrap-based UI with real-time updates

### 📊 Key Metrics Monitored

1. **Performance Metrics**
   - Evaluation latency (p50, p95, p99 percentiles)
   - Evaluations per minute
   - Decision distribution (allow/deny/review)
   - System throughput and response times

2. **Security Metrics**
   - Policy violations by type and severity
   - High-risk decision counts
   - Semantic signal detection rates
   - Security status indicators

3. **Risk Assessment**
   - Risk score distribution (low/medium/high)
   - Deviation score trends
   - Compliance rate tracking
   - Threat level indicators

4. **System Health**
   - Policy engine status
   - OPA server connectivity
   - Emergency system readiness
   - Metrics collection health

### 🔔 Advanced Alerting System

#### Alert Channels
- **Email Notifications**: SMTP-based email alerts with HTML templates
- **Webhook Integration**: HTTP/HTTPS webhook delivery
- **Slack Integration**: Native Slack webhook support
- **Console Logging**: Structured log-based alerts

#### Alert Conditions
- **Threshold-based**: Metric value exceeds/falls below thresholds
- **Duration-based**: Conditions persist for specified time periods
- **Rate-based**: Event frequency exceeds limits
- **Severity-based**: Automatic escalation by severity level

#### Escalation Rules
- **Automatic Escalation**: Time-based or count-based escalation
- **Multi-channel Notification**: Send to additional channels
- **Emergency Shutdown**: Automatic system shutdown for critical threats

### 📈 Compliance and Reporting

- **Policy Compliance Trends**: 24-hour compliance rate visualization
- **Violation Tracking**: Detailed violation counts and patterns
- **Risk Distribution Analysis**: Statistical risk assessment reporting
- **Audit Trail Integration**: Complete decision traceability

## Configuration

### Environment Variables

```bash
# Dashboard Configuration
GUARDIAL_DASHBOARD_HOST=0.0.0.0
GUARDIAL_DASHBOARD_PORT=8080

# Email Alerting (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@yourcompany.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=security-team@yourcompany.com

# Webhook Alerting (Optional)
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

### Alerting Configuration File

Create `alerting_config.json` in the guardial directory:

```json
{
  "channels": [
    {
      "name": "security_email",
      "channel_type": "email",
      "config": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "alerts@company.com",
        "smtp_password": "password",
        "from_email": "alerts@company.com",
        "to_emails": ["security@company.com"],
        "use_tls": true
      },
      "enabled": true,
      "severity_filter": ["warning", "error", "critical"]
    }
  ],
  "escalation_rules": [
    {
      "name": "critical_immediate",
      "condition": "severity",
      "threshold": "critical",
      "action": "notify_additional",
      "target_channels": ["security_email"],
      "enabled": true
    }
  ]
}
```

## API Endpoints

### Metrics Endpoints

- `GET /api/metrics/performance` - Current performance metrics
- `GET /api/metrics/security` - Security-specific metrics  
- `GET /api/metrics/system` - System health metrics
- `GET /api/alerts` - Active alerts list
- `GET /api/compliance/trends` - Policy compliance trends
- `GET /api/risk/distribution` - Risk assessment distribution

### Control Endpoints

- `POST /api/alerts/configure` - Configure new alert conditions
- `POST /api/emergency/shutdown` - Trigger emergency shutdown

### Real-time Updates

- `WebSocket /ws/metrics` - Real-time metrics streaming

## Usage

### Starting the Dashboard

The dashboard starts automatically with the Guardial agent:

```bash
cd abi-core/agents/guardial
python agent/main.py
```

Access the dashboard at: `http://localhost:8080`

### Manual Dashboard Startup

```python
from agent.dashboard import start_dashboard_server

# Start dashboard on custom host/port
start_dashboard_server(host="0.0.0.0", port=8080)
```

### Configuring Alerts

```python
from agent.alerting_system import get_alerting_system, AlertChannel

alerting = get_alerting_system()

# Add email channel
email_channel = AlertChannel(
    name="security_team",
    channel_type="email",
    config={
        "smtp_server": "smtp.company.com",
        "smtp_port": 587,
        "smtp_user": "alerts@company.com",
        "smtp_password": "password",
        "from_email": "guardial@company.com",
        "to_emails": ["security@company.com"]
    }
)
alerting.add_channel(email_channel)
```

### Recording Custom Metrics

```python
from agent.metrics_collector import get_metrics_collector

metrics = get_metrics_collector()

# Record evaluation metrics
metrics.record_evaluation_latency(150.5, {"agent": "planner"})
metrics.record_decision("deny", 0.85, {"user": "user123"})
metrics.record_policy_violation("unauthorized_access", "high")
```

## Dashboard Features

### Main Dashboard View

1. **Key Metrics Cards**
   - Evaluations per minute
   - Average latency
   - High-risk actions count
   - Policy violations count

2. **Interactive Charts**
   - Decision distribution pie chart
   - Risk score distribution bar chart
   - Performance trends line chart

3. **System Health Panel**
   - Policy engine status
   - OPA server status
   - Emergency system status
   - Metrics collection status

4. **Active Alerts Panel**
   - Real-time alert display
   - Severity-based color coding
   - Alert duration tracking
   - Alert acknowledgment

### Emergency Controls

- **Emergency Shutdown Button**: Immediate system shutdown capability
- **Reason Logging**: Required justification for emergency actions
- **Audit Trail**: Complete logging of emergency actions

## Alert Templates

### Security Alert Template

```
Subject: 🚨 Guardial Security Alert: {alert_type}

Security Alert Details:
- Alert Type: {alert_type}
- Severity: {severity}
- Message: {message}
- Timestamp: {timestamp}
- Metric: {metric_name} = {current_value}
- Threshold: {threshold}
- Duration: {duration_seconds} seconds

System Status: {system_status}
```

### Emergency Alert Template

```
Subject: 🚨 EMERGENCY: Guardial System Alert

EMERGENCY SYSTEM ALERT

Emergency Type: {emergency_type}
Emergency Level: {emergency_level}
Reason: {reason}
Initiated By: {initiated_by}
Timestamp: {timestamp}

IMMEDIATE ACTION REQUIRED
```

## Testing

Run the comprehensive test suite:

```bash
cd abi-core/agents/guardial
python test_dashboard_alerting.py
```

Test coverage includes:
- Metrics collection functionality
- Alert condition triggering
- Dashboard API endpoints
- Real-time updates
- Compliance reporting
- Emergency procedures

## Security Considerations

1. **Access Control**: Dashboard should be behind authentication in production
2. **HTTPS**: Use TLS encryption for dashboard access
3. **Alert Security**: Secure webhook URLs and email credentials
4. **Rate Limiting**: Implement rate limiting for API endpoints
5. **Audit Logging**: All dashboard actions are logged for audit

## Performance

- **Real-time Updates**: 5-second refresh intervals
- **Metric Retention**: 24-hour default retention with configurable cleanup
- **Alert Processing**: Sub-second alert evaluation and delivery
- **Dashboard Response**: <100ms API response times
- **Memory Usage**: Efficient circular buffers for metric storage

## Troubleshooting

### Common Issues

1. **Dashboard Not Starting**
   - Check port availability (default 8080)
   - Verify FastAPI dependencies installed
   - Check log files for startup errors

2. **Alerts Not Sending**
   - Verify SMTP/webhook configuration
   - Check network connectivity
   - Review alerting_config.json syntax

3. **Missing Metrics**
   - Ensure metrics collector is initialized
   - Check for metric recording in application code
   - Verify metric retention settings

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('agent.dashboard').setLevel(logging.DEBUG)
logging.getLogger('agent.alerting_system').setLevel(logging.DEBUG)
```

## Integration

The dashboard and alerting system integrate seamlessly with:

- **Guardial Security Engine**: Automatic metric collection
- **Emergency Response System**: Coordinated emergency procedures  
- **Policy Engine**: Policy violation tracking
- **Audit System**: Complete audit trail integration
- **MCP Interface**: Evaluation metrics from MCP calls

## Requirements Compliance

This implementation fulfills all Task 5.4 requirements:

✅ **Real-time security status dashboard with key metrics**
✅ **Policy compliance trend visualization and reporting**  
✅ **Risk assessment distribution charts and analysis**
✅ **System health indicators with status monitoring**
✅ **Automated alerting for critical security events and thresholds**

## Future Enhancements

- Mobile-responsive dashboard improvements
- Advanced analytics and ML-based anomaly detection
- Integration with external SIEM systems
- Custom dashboard widgets and layouts
- Multi-tenant dashboard support