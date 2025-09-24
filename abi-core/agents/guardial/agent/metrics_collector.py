"""
Metrics Collection System for Guardial Agent

This module implements real-time metrics collection, monitoring,
and alerting for the Guardial security system.
"""

import time
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
import statistics

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)

@dataclass
class AlertCondition:
    """Alert condition configuration"""
    metric_name: str
    threshold: float
    operator: str  # >, <, >=, <=, ==
    duration_seconds: int = 60
    severity: str = "warning"  # info, warning, error, critical
    message_template: str = "Alert: {metric_name} {operator} {threshold}"

class MetricsCollector:
    """Real-time metrics collection and monitoring"""
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.alert_conditions: List[AlertCondition] = []
        self.active_alerts: Dict[str, datetime] = {}
        
        # Performance tracking
        self.evaluation_times: deque = deque(maxlen=1000)
        self.decision_counts: Dict[str, int] = defaultdict(int)
        self.risk_scores: deque = deque(maxlen=1000)
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_old_metrics())
    
    def record_evaluation_latency(self, latency_ms: float, labels: Optional[Dict[str, str]] = None):
        """Record evaluation latency metric"""
        self.evaluation_times.append(latency_ms)
        self._add_metric("evaluation_latency_ms", latency_ms, labels or {})
        
        # Update histogram
        self.histograms["evaluation_latency_ms"].append(latency_ms)
        if len(self.histograms["evaluation_latency_ms"]) > 1000:
            self.histograms["evaluation_latency_ms"] = self.histograms["evaluation_latency_ms"][-1000:]
    
    def record_decision(self, decision: str, deviation_score: float, labels: Optional[Dict[str, str]] = None):
        """Record policy decision metric"""
        self.decision_counts[decision] += 1
        self.counters[f"decisions_{decision}"] += 1
        
        self.risk_scores.append(deviation_score)
        combined_labels = (labels or {}).copy()
        combined_labels["decision"] = decision
        self._add_metric("deviation_score", deviation_score, combined_labels)
        
        # Track high-risk decisions
        if deviation_score > 0.8:
            self.counters["high_risk_decisions"] += 1
            self._add_metric("high_risk_decision", 1.0, labels or {})
    
    def record_policy_violation(self, violation_type: str, severity: str, labels: Optional[Dict[str, str]] = None):
        """Record policy violation metric"""
        self.counters[f"violations_{violation_type}"] += 1
        self.counters[f"violations_severity_{severity}"] += 1
        
        combined_labels = (labels or {}).copy()
        combined_labels["violation_type"] = violation_type
        combined_labels["severity"] = severity
        self._add_metric("policy_violation", 1.0, combined_labels)
    
    def record_semantic_signal(self, signal_type: str, confidence: float, labels: Optional[Dict[str, str]] = None):
        """Record semantic signal detection metric"""
        self.counters[f"semantic_signals_{signal_type}"] += 1
        combined_labels = (labels or {}).copy()
        combined_labels["signal_type"] = signal_type
        self._add_metric("semantic_signal_confidence", confidence, combined_labels)
    
    def record_system_event(self, event_type: str, labels: Optional[Dict[str, str]] = None):
        """Record system event metric"""
        self.counters[f"system_events_{event_type}"] += 1
        combined_labels = (labels or {}).copy()
        combined_labels["event_type"] = event_type
        self._add_metric("system_event", 1.0, combined_labels)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set gauge metric value"""
        self.gauges[name] = value
        self._add_metric(name, value, labels or {})
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment counter metric"""
        self.counters[name] += value
        self._add_metric(name, self.counters[name], labels or {})
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        now = datetime.utcnow()
        
        # Calculate latency percentiles
        latencies = list(self.evaluation_times)
        latency_stats = {}
        if latencies:
            latency_stats = {
                "p50": statistics.median(latencies),
                "p95": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
                "p99": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies),
                "avg": statistics.mean(latencies),
                "min": min(latencies),
                "max": max(latencies)
            }
        
        # Calculate risk score distribution
        risk_scores = list(self.risk_scores)
        risk_stats = {}
        if risk_scores:
            risk_stats = {
                "avg": statistics.mean(risk_scores),
                "median": statistics.median(risk_scores),
                "high_risk_count": len([s for s in risk_scores if s > 0.8]),
                "medium_risk_count": len([s for s in risk_scores if 0.5 <= s <= 0.8]),
                "low_risk_count": len([s for s in risk_scores if s < 0.5])
            }
        
        # Decision distribution
        total_decisions = sum(self.decision_counts.values())
        decision_distribution = {}
        if total_decisions > 0:
            decision_distribution = {
                decision: (count / total_decisions) * 100
                for decision, count in self.decision_counts.items()
            }
        
        return {
            "timestamp": now.isoformat(),
            "evaluation_latency": latency_stats,
            "risk_score_distribution": risk_stats,
            "decision_distribution": decision_distribution,
            "total_evaluations": len(self.evaluation_times),
            "total_decisions": total_decisions,
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "active_alerts": len(self.active_alerts)
        }
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security-specific metrics"""
        now = datetime.utcnow()
        
        # Policy violations in last hour
        hour_ago = now - timedelta(hours=1)
        recent_violations = self._count_recent_metrics("policy_violation", hour_ago)
        
        # High-risk decisions in last hour
        recent_high_risk = self._count_recent_metrics("high_risk_decision", hour_ago)
        
        # System events
        system_events = {
            key: value for key, value in self.counters.items()
            if key.startswith("system_events_")
        }
        
        return {
            "timestamp": now.isoformat(),
            "policy_violations_last_hour": recent_violations,
            "high_risk_decisions_last_hour": recent_high_risk,
            "total_violations": sum(v for k, v in self.counters.items() if k.startswith("violations_")),
            "total_high_risk_decisions": self.counters.get("high_risk_decisions", 0),
            "system_events": system_events,
            "security_status": self._calculate_security_status()
        }
    
    def add_alert_condition(self, condition: AlertCondition):
        """Add alert condition for monitoring"""
        self.alert_conditions.append(condition)
        logger.info(f"Added alert condition: {condition.metric_name} {condition.operator} {condition.threshold}")
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check all alert conditions and return active alerts"""
        active_alerts = []
        now = datetime.utcnow()
        
        for condition in self.alert_conditions:
            alert_key = f"{condition.metric_name}_{condition.operator}_{condition.threshold}"
            
            # Get recent values for the metric
            recent_values = self._get_recent_metric_values(
                condition.metric_name,
                now - timedelta(seconds=condition.duration_seconds)
            )
            
            if not recent_values:
                continue
            
            # Check if condition is met
            latest_value = recent_values[-1].value
            condition_met = self._evaluate_condition(latest_value, condition.operator, condition.threshold)
            
            if condition_met:
                if alert_key not in self.active_alerts:
                    # New alert
                    self.active_alerts[alert_key] = now
                    alert = {
                        "alert_key": alert_key,
                        "metric_name": condition.metric_name,
                        "current_value": latest_value,
                        "threshold": condition.threshold,
                        "operator": condition.operator,
                        "severity": condition.severity,
                        "message": condition.message_template.format(
                            metric_name=condition.metric_name,
                            operator=condition.operator,
                            threshold=condition.threshold,
                            current_value=latest_value
                        ),
                        "started_at": now.isoformat(),
                        "duration_seconds": 0
                    }
                    active_alerts.append(alert)
                    logger.warning(f"🚨 Alert triggered: {alert['message']}")
                    
                    # Send alert notification
                    asyncio.create_task(self._send_alert_notification(alert))
                    
                else:
                    # Existing alert
                    started_at = self.active_alerts[alert_key]
                    duration = (now - started_at).total_seconds()
                    alert = {
                        "alert_key": alert_key,
                        "metric_name": condition.metric_name,
                        "current_value": latest_value,
                        "threshold": condition.threshold,
                        "operator": condition.operator,
                        "severity": condition.severity,
                        "message": condition.message_template.format(
                            metric_name=condition.metric_name,
                            operator=condition.operator,
                            threshold=condition.threshold,
                            current_value=latest_value
                        ),
                        "started_at": started_at.isoformat(),
                        "duration_seconds": int(duration)
                    }
                    active_alerts.append(alert)
            else:
                # Condition no longer met, clear alert
                if alert_key in self.active_alerts:
                    del self.active_alerts[alert_key]
                    logger.info(f"✅ Alert cleared: {condition.metric_name}")
                    
                    # Send alert cleared notification
                    asyncio.create_task(self._send_alert_cleared_notification(condition.metric_name))
        
        return active_alerts
    
    def _add_metric(self, name: str, value: float, labels: Dict[str, str]):
        """Add metric point to time series"""
        point = MetricPoint(
            timestamp=datetime.utcnow(),
            value=value,
            labels=labels
        )
        self.metrics[name].append(point)
    
    def _count_recent_metrics(self, metric_name: str, since: datetime) -> int:
        """Count metric occurrences since given time"""
        if metric_name not in self.metrics:
            return 0
        
        return len([
            point for point in self.metrics[metric_name]
            if point.timestamp >= since
        ])
    
    def _get_recent_metric_values(self, metric_name: str, since: datetime) -> List[MetricPoint]:
        """Get metric values since given time"""
        if metric_name not in self.metrics:
            return []
        
        return [
            point for point in self.metrics[metric_name]
            if point.timestamp >= since
        ]
    
    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate alert condition"""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        else:
            logger.error(f"Unknown operator: {operator}")
            return False
    
    def _calculate_security_status(self) -> str:
        """Calculate overall security status"""
        # Check for critical violations in last hour
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        critical_violations = self._count_recent_metrics("policy_violation", hour_ago)
        
        # Check high-risk decisions
        high_risk_decisions = self.counters.get("high_risk_decisions", 0)
        total_decisions = sum(self.decision_counts.values())
        
        if critical_violations > 10:
            return "CRITICAL"
        elif critical_violations > 5:
            return "HIGH_RISK"
        elif total_decisions > 0 and (high_risk_decisions / total_decisions) > 0.3:
            return "ELEVATED"
        elif len(self.active_alerts) > 0:
            return "WARNING"
        else:
            return "NORMAL"
    
    async def _send_alert_notification(self, alert: Dict[str, Any]):
        """Send alert notification through alerting system"""
        try:
            # Import here to avoid circular imports
            from agent.alerting_system import get_alerting_system
            
            alerting_system = get_alerting_system()
            
            alert_data = {
                "alert_type": f"Metric Threshold Exceeded: {alert['metric_name']}",
                "severity": alert["severity"],
                "message": alert["message"],
                "timestamp": alert["started_at"],
                "metric_name": alert["metric_name"],
                "current_value": alert["current_value"],
                "threshold": alert["threshold"],
                "duration_seconds": alert["duration_seconds"],
                "system_status": self._calculate_security_status()
            }
            
            await alerting_system.send_alert(alert_data)
            
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
    
    async def _send_alert_cleared_notification(self, metric_name: str):
        """Send alert cleared notification"""
        try:
            # Import here to avoid circular imports
            from agent.alerting_system import get_alerting_system
            
            alerting_system = get_alerting_system()
            
            alert_data = {
                "alert_type": f"Alert Cleared: {metric_name}",
                "severity": "info",
                "message": f"Alert condition for {metric_name} has been resolved",
                "timestamp": datetime.utcnow().isoformat(),
                "metric_name": metric_name,
                "current_value": "RESOLVED",
                "threshold": "N/A",
                "duration_seconds": 0,
                "system_status": self._calculate_security_status()
            }
            
            await alerting_system.send_alert(alert_data)
            
        except Exception as e:
            logger.error(f"Failed to send alert cleared notification: {e}")
    
    async def _cleanup_old_metrics(self):
        """Cleanup old metrics periodically"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)
                
                for metric_name, points in self.metrics.items():
                    # Remove old points
                    while points and points[0].timestamp < cutoff_time:
                        points.popleft()
                
                logger.info(f"Cleaned up metrics older than {self.retention_hours} hours")
                
            except Exception as e:
                logger.error(f"Metrics cleanup failed: {e}")


# Singleton instance
_metrics_collector = None

def get_metrics_collector() -> MetricsCollector:
    """Get singleton metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
        
        # Add default alert conditions
        _metrics_collector.add_alert_condition(AlertCondition(
            metric_name="evaluation_latency_ms",
            threshold=5000.0,
            operator=">",
            duration_seconds=300,
            severity="warning",
            message_template="High evaluation latency: {current_value}ms > {threshold}ms"
        ))
        
        _metrics_collector.add_alert_condition(AlertCondition(
            metric_name="deviation_score",
            threshold=0.9,
            operator=">",
            duration_seconds=60,
            severity="critical",
            message_template="Critical risk score detected: {current_value} > {threshold}"
        ))
        
        _metrics_collector.add_alert_condition(AlertCondition(
            metric_name="policy_violation",
            threshold=10.0,
            operator=">",
            duration_seconds=3600,
            severity="error",
            message_template="High policy violation rate: {current_value} violations/hour"
        ))
        
        # Add more comprehensive alert conditions
        _metrics_collector.add_alert_condition(AlertCondition(
            metric_name="high_risk_decisions",
            threshold=5.0,
            operator=">",
            duration_seconds=300,
            severity="warning",
            message_template="High number of risky decisions: {current_value} in 5 minutes"
        ))
        
        _metrics_collector.add_alert_condition(AlertCondition(
            metric_name="system_event",
            threshold=1.0,
            operator=">=",
            duration_seconds=60,
            severity="info",
            message_template="System event detected: {current_value}"
        ))
    
    return _metrics_collector