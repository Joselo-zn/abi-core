"""
Real-time Security Monitoring Dashboard for Guardial Agent

This module implements a comprehensive web-based dashboard for monitoring
security metrics, policy compliance, risk assessments, and system health.
"""

import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from agent.metrics_collector import get_metrics_collector, AlertCondition
from agent.emergency_response import get_emergency_response_system

logger = logging.getLogger(__name__)

class SecurityDashboard:
    """Real-time security monitoring dashboard"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Guardial Security Dashboard", version="1.0.0")
        self.metrics_collector = get_metrics_collector()
        self.emergency_system = get_emergency_response_system()
        self.active_connections: List[WebSocket] = []
        
        # Setup routes
        self._setup_routes()
        
        # Setup static files and templates
        self._setup_static_files()
        
        # Background tasks will be started when the event loop is running
        self._background_tasks_started = False
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Main dashboard page"""
            return self._render_dashboard_template(request)
        
        @self.app.get("/api/metrics/performance")
        async def get_performance_metrics():
            """Get current performance metrics"""
            return JSONResponse(self.metrics_collector.get_performance_metrics())
        
        @self.app.get("/api/metrics/security")
        async def get_security_metrics():
            """Get current security metrics"""
            return JSONResponse(self.metrics_collector.get_security_metrics())
        
        @self.app.get("/api/metrics/system")
        async def get_system_metrics():
            """Get system health metrics"""
            return JSONResponse(await self._get_system_health_metrics())
        
        @self.app.get("/api/alerts")
        async def get_active_alerts():
            """Get currently active alerts"""
            alerts = self.metrics_collector.check_alerts()
            return JSONResponse({"alerts": alerts, "count": len(alerts)})
        
        @self.app.get("/api/compliance/trends")
        async def get_compliance_trends():
            """Get policy compliance trend data"""
            return JSONResponse(await self._get_compliance_trends())
        
        @self.app.get("/api/risk/distribution")
        async def get_risk_distribution():
            """Get risk assessment distribution data"""
            return JSONResponse(await self._get_risk_distribution())
        
        @self.app.post("/api/alerts/configure")
        async def configure_alert(alert_config: dict):
            """Configure new alert condition"""
            try:
                condition = AlertCondition(
                    metric_name=alert_config["metric_name"],
                    threshold=float(alert_config["threshold"]),
                    operator=alert_config["operator"],
                    duration_seconds=int(alert_config.get("duration_seconds", 60)),
                    severity=alert_config.get("severity", "warning"),
                    message_template=alert_config.get("message_template", 
                        "Alert: {metric_name} {operator} {threshold}")
                )
                self.metrics_collector.add_alert_condition(condition)
                return JSONResponse({"status": "success", "message": "Alert configured"})
            except Exception as e:
                logger.error(f"Failed to configure alert: {e}")
                return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
        
        @self.app.post("/api/emergency/shutdown")
        async def emergency_shutdown(request: Request):
            """Trigger emergency shutdown"""
            try:
                body = await request.json()
                reason = body.get("reason", "Manual emergency shutdown from dashboard")
                
                from agent.emergency_response import EmergencyType, EmergencyLevel
                await self.emergency_system.emergency_shutdown(
                    reason=reason,
                    initiated_by="DASHBOARD_USER",
                    emergency_type=EmergencyType.MANUAL_INTERVENTION,
                    emergency_level=EmergencyLevel.HIGH
                )
                
                return JSONResponse({"status": "success", "message": "Emergency shutdown initiated"})
            except Exception as e:
                logger.error(f"Emergency shutdown failed: {e}")
                return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
        
        @self.app.websocket("/ws/metrics")
        async def websocket_metrics(websocket: WebSocket):
            """WebSocket endpoint for real-time metrics"""
            await websocket.accept()
            self.active_connections.append(websocket)
            
            try:
                while True:
                    # Keep connection alive
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
    
    def _setup_static_files(self):
        """Setup static files and templates"""
        # Create dashboard directory if it doesn't exist
        dashboard_dir = Path(__file__).parent / "dashboard_static"
        dashboard_dir.mkdir(exist_ok=True)
        
        # Create templates directory
        templates_dir = dashboard_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        # Create static directory
        static_dir = dashboard_dir / "static"
        static_dir.mkdir(exist_ok=True)
        
        # Setup Jinja2 templates
        self.templates = Jinja2Templates(directory=str(templates_dir))
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Create dashboard template if it doesn't exist
        self._create_dashboard_template(templates_dir)
        self._create_dashboard_assets(static_dir)
    
    def _create_dashboard_template(self, templates_dir: Path):
        """Create the main dashboard HTML template"""
        template_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guardial Security Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/date-fns@2.29.3/index.min.js"></script>
    <link href="/static/dashboard.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container-fluid">
            <span class="navbar-brand mb-0 h1">
                <i class="fas fa-shield-alt"></i> Guardial Security Dashboard
            </span>
            <div class="navbar-nav flex-row">
                <div class="nav-item me-3">
                    <span class="badge" id="system-status">Loading...</span>
                </div>
                <div class="nav-item">
                    <button class="btn btn-danger btn-sm" id="emergency-btn" onclick="showEmergencyModal()">
                        <i class="fas fa-exclamation-triangle"></i> Emergency
                    </button>
                </div>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-3">
        <!-- Alert Banner -->
        <div id="alert-banner" class="alert alert-warning alert-dismissible d-none" role="alert">
            <strong>Active Alerts:</strong> <span id="alert-count">0</span>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>

        <!-- Key Metrics Row -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6 class="card-title text-muted">Evaluations/Min</h6>
                                <h3 class="mb-0" id="evaluations-per-min">0</h3>
                            </div>
                            <div class="metric-icon bg-primary">
                                <i class="fas fa-tachometer-alt"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6 class="card-title text-muted">Avg Latency</h6>
                                <h3 class="mb-0" id="avg-latency">0ms</h3>
                            </div>
                            <div class="metric-icon bg-info">
                                <i class="fas fa-clock"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6 class="card-title text-muted">High Risk Actions</h6>
                                <h3 class="mb-0" id="high-risk-count">0</h3>
                            </div>
                            <div class="metric-icon bg-warning">
                                <i class="fas fa-exclamation-triangle"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6 class="card-title text-muted">Policy Violations</h6>
                                <h3 class="mb-0" id="violations-count">0</h3>
                            </div>
                            <div class="metric-icon bg-danger">
                                <i class="fas fa-ban"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Decision Distribution</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="decision-chart"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Risk Score Distribution</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="risk-chart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- Performance and Compliance Row -->
        <div class="row mb-4">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Performance Trends</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="performance-chart"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">System Health</h5>
                    </div>
                    <div class="card-body">
                        <div class="health-indicator">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span>Policy Engine</span>
                                <span class="badge bg-success" id="policy-status">OK</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span>OPA Server</span>
                                <span class="badge bg-success" id="opa-status">OK</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span>Emergency System</span>
                                <span class="badge bg-success" id="emergency-status">OK</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <span>Metrics Collection</span>
                                <span class="badge bg-success" id="metrics-status">OK</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Active Alerts -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Active Alerts</h5>
                    </div>
                    <div class="card-body">
                        <div id="alerts-container">
                            <p class="text-muted">No active alerts</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Emergency Shutdown Modal -->
    <div class="modal fade" id="emergencyModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header bg-danger text-white">
                    <h5 class="modal-title">Emergency Shutdown</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p><strong>Warning:</strong> This will immediately shut down all agents and block all operations.</p>
                    <div class="mb-3">
                        <label for="shutdown-reason" class="form-label">Reason for shutdown:</label>
                        <textarea class="form-control" id="shutdown-reason" rows="3" 
                                  placeholder="Describe the security incident or reason for emergency shutdown..."></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-danger" onclick="executeEmergencyShutdown()">
                        <i class="fas fa-power-off"></i> Emergency Shutdown
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/dashboard.js"></script>
</body>
</html>'''
        
        template_file = templates_dir / "dashboard.html"
        template_file.write_text(template_content)
    
    def _create_dashboard_assets(self, static_dir: Path):
        """Create dashboard CSS and JavaScript assets"""
        
        # CSS
        css_content = '''
.metric-card {
    border: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: transform 0.2s;
}

.metric-card:hover {
    transform: translateY(-2px);
}

.metric-icon {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.2rem;
}

.health-indicator {
    font-size: 0.9rem;
}

.alert-item {
    border-left: 4px solid;
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 4px;
}

.alert-critical {
    border-left-color: #dc3545;
    background-color: #f8d7da;
}

.alert-error {
    border-left-color: #fd7e14;
    background-color: #fff3cd;
}

.alert-warning {
    border-left-color: #ffc107;
    background-color: #fff3cd;
}

.alert-info {
    border-left-color: #0dcaf0;
    background-color: #d1ecf1;
}

#system-status {
    font-size: 0.8rem;
    padding: 0.25rem 0.5rem;
}

.status-normal { background-color: #198754 !important; }
.status-warning { background-color: #ffc107 !important; color: #000 !important; }
.status-elevated { background-color: #fd7e14 !important; }
.status-high-risk { background-color: #dc3545 !important; }
.status-critical { background-color: #6f42c1 !important; }
'''
        
        css_file = static_dir / "dashboard.css"
        css_file.write_text(css_content)
        
        # JavaScript
        js_content = '''
class SecurityDashboard {
    constructor() {
        this.ws = null;
        this.charts = {};
        this.initWebSocket();
        this.initCharts();
        this.startDataRefresh();
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/metrics`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.updateDashboard(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected, reconnecting...');
            setTimeout(() => this.initWebSocket(), 5000);
        };
    }

    initCharts() {
        // Decision Distribution Chart
        const decisionCtx = document.getElementById('decision-chart').getContext('2d');
        this.charts.decision = new Chart(decisionCtx, {
            type: 'doughnut',
            data: {
                labels: ['Allow', 'Deny', 'Review'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#198754', '#dc3545', '#ffc107']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });

        // Risk Distribution Chart
        const riskCtx = document.getElementById('risk-chart').getContext('2d');
        this.charts.risk = new Chart(riskCtx, {
            type: 'bar',
            data: {
                labels: ['Low Risk', 'Medium Risk', 'High Risk'],
                datasets: [{
                    label: 'Count',
                    data: [0, 0, 0],
                    backgroundColor: ['#198754', '#ffc107', '#dc3545']
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });

        // Performance Trends Chart
        const perfCtx = document.getElementById('performance-chart').getContext('2d');
        this.charts.performance = new Chart(perfCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Avg Latency (ms)',
                    data: [],
                    borderColor: '#0d6efd',
                    tension: 0.1
                }, {
                    label: 'Evaluations/min',
                    data: [],
                    borderColor: '#198754',
                    tension: 0.1,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    }

    async startDataRefresh() {
        setInterval(async () => {
            await this.refreshMetrics();
            await this.refreshAlerts();
        }, 5000);
        
        // Initial load
        await this.refreshMetrics();
        await this.refreshAlerts();
    }

    async refreshMetrics() {
        try {
            const [performance, security, system] = await Promise.all([
                fetch('/api/metrics/performance').then(r => r.json()),
                fetch('/api/metrics/security').then(r => r.json()),
                fetch('/api/metrics/system').then(r => r.json())
            ]);

            this.updateMetrics(performance, security, system);
        } catch (error) {
            console.error('Failed to refresh metrics:', error);
        }
    }

    async refreshAlerts() {
        try {
            const response = await fetch('/api/alerts');
            const data = await response.json();
            this.updateAlerts(data.alerts);
        } catch (error) {
            console.error('Failed to refresh alerts:', error);
        }
    }

    updateMetrics(performance, security, system) {
        // Update key metrics
        document.getElementById('evaluations-per-min').textContent = 
            Math.round((performance.total_evaluations || 0) / 60);
        
        document.getElementById('avg-latency').textContent = 
            `${Math.round(performance.evaluation_latency?.avg || 0)}ms`;
        
        document.getElementById('high-risk-count').textContent = 
            performance.risk_score_distribution?.high_risk_count || 0;
        
        document.getElementById('violations-count').textContent = 
            security.total_violations || 0;

        // Update system status
        const statusElement = document.getElementById('system-status');
        const status = security.security_status || 'UNKNOWN';
        statusElement.textContent = status;
        statusElement.className = `badge status-${status.toLowerCase().replace('_', '-')}`;

        // Update decision chart
        if (performance.decision_distribution) {
            const dist = performance.decision_distribution;
            this.charts.decision.data.datasets[0].data = [
                dist.allow || 0,
                dist.deny || 0,
                dist.review || 0
            ];
            this.charts.decision.update();
        }

        // Update risk chart
        if (performance.risk_score_distribution) {
            const risk = performance.risk_score_distribution;
            this.charts.risk.data.datasets[0].data = [
                risk.low_risk_count || 0,
                risk.medium_risk_count || 0,
                risk.high_risk_count || 0
            ];
            this.charts.risk.update();
        }

        // Update performance chart (simplified for now)
        const now = new Date().toLocaleTimeString();
        if (this.charts.performance.data.labels.length > 20) {
            this.charts.performance.data.labels.shift();
            this.charts.performance.data.datasets[0].data.shift();
            this.charts.performance.data.datasets[1].data.shift();
        }
        
        this.charts.performance.data.labels.push(now);
        this.charts.performance.data.datasets[0].data.push(
            performance.evaluation_latency?.avg || 0
        );
        this.charts.performance.data.datasets[1].data.push(
            Math.round((performance.total_evaluations || 0) / 60)
        );
        this.charts.performance.update();

        // Update system health indicators
        this.updateHealthIndicators(system);
    }

    updateHealthIndicators(system) {
        const indicators = {
            'policy-status': system.policy_engine_status || 'OK',
            'opa-status': system.opa_status || 'OK',
            'emergency-status': system.emergency_system_status || 'OK',
            'metrics-status': system.metrics_status || 'OK'
        };

        Object.entries(indicators).forEach(([id, status]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = status;
                element.className = `badge ${status === 'OK' ? 'bg-success' : 'bg-danger'}`;
            }
        });
    }

    updateAlerts(alerts) {
        const container = document.getElementById('alerts-container');
        const banner = document.getElementById('alert-banner');
        const countElement = document.getElementById('alert-count');

        if (alerts.length === 0) {
            container.innerHTML = '<p class="text-muted">No active alerts</p>';
            banner.classList.add('d-none');
        } else {
            banner.classList.remove('d-none');
            countElement.textContent = alerts.length;

            container.innerHTML = alerts.map(alert => `
                <div class="alert-item alert-${alert.severity}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong>${alert.severity.toUpperCase()}</strong>
                            <p class="mb-1">${alert.message}</p>
                            <small class="text-muted">
                                Started: ${new Date(alert.started_at).toLocaleString()}
                                ${alert.duration_seconds > 0 ? `(${Math.round(alert.duration_seconds/60)}m ago)` : ''}
                            </small>
                        </div>
                        <span class="badge bg-secondary">${alert.metric_name}</span>
                    </div>
                </div>
            `).join('');
        }
    }
}

function showEmergencyModal() {
    const modal = new bootstrap.Modal(document.getElementById('emergencyModal'));
    modal.show();
}

async function executeEmergencyShutdown() {
    const reason = document.getElementById('shutdown-reason').value;
    if (!reason.trim()) {
        alert('Please provide a reason for the emergency shutdown.');
        return;
    }

    try {
        const response = await fetch('/api/emergency/shutdown', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ reason })
        });

        const result = await response.json();
        
        if (result.status === 'success') {
            alert('Emergency shutdown initiated successfully.');
            const modal = bootstrap.Modal.getInstance(document.getElementById('emergencyModal'));
            modal.hide();
        } else {
            alert(`Emergency shutdown failed: ${result.message}`);
        }
    } catch (error) {
        alert(`Emergency shutdown failed: ${error.message}`);
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new SecurityDashboard();
});
'''
        
        js_file = static_dir / "dashboard.js"
        js_file.write_text(js_content)
    
    def _render_dashboard_template(self, request: Request):
        """Render the main dashboard template"""
        return self.templates.TemplateResponse("dashboard.html", {"request": request})
    
    async def _get_system_health_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system health metrics"""
        try:
            # Check policy engine status
            policy_status = "OK"
            try:
                # This would check if the policy engine is responsive
                policy_status = "OK"
            except Exception:
                policy_status = "ERROR"
            
            # Check OPA server status
            opa_status = "OK"
            try:
                # This would ping the OPA server
                opa_status = "OK"
            except Exception:
                opa_status = "ERROR"
            
            # Check emergency system status
            emergency_status = "OK"
            try:
                if self.emergency_system.is_emergency_active():
                    emergency_status = "EMERGENCY_ACTIVE"
                else:
                    emergency_status = "OK"
            except Exception:
                emergency_status = "ERROR"
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "policy_engine_status": policy_status,
                "opa_status": opa_status,
                "emergency_system_status": emergency_status,
                "metrics_status": "OK",
                "uptime_seconds": (datetime.utcnow() - datetime.utcnow()).total_seconds(),
                "memory_usage_mb": 0,  # Would implement actual memory monitoring
                "cpu_usage_percent": 0  # Would implement actual CPU monitoring
            }
        except Exception as e:
            logger.error(f"Failed to get system health metrics: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "policy_engine_status": "ERROR",
                "opa_status": "ERROR",
                "emergency_system_status": "ERROR",
                "metrics_status": "ERROR",
                "error": str(e)
            }
    
    async def _get_compliance_trends(self) -> Dict[str, Any]:
        """Get policy compliance trend data"""
        try:
            # Get metrics for the last 24 hours
            now = datetime.utcnow()
            hours = []
            compliance_rates = []
            violation_counts = []
            
            for i in range(24):
                hour_start = now - timedelta(hours=i+1)
                hour_end = now - timedelta(hours=i)
                
                # This would calculate actual compliance metrics for each hour
                # For now, return sample data structure
                hours.append(hour_start.strftime("%H:00"))
                compliance_rates.append(95.0)  # Sample compliance rate
                violation_counts.append(2)     # Sample violation count
            
            return {
                "timestamp": now.isoformat(),
                "time_labels": list(reversed(hours)),
                "compliance_rates": list(reversed(compliance_rates)),
                "violation_counts": list(reversed(violation_counts)),
                "average_compliance": sum(compliance_rates) / len(compliance_rates),
                "total_violations_24h": sum(violation_counts)
            }
        except Exception as e:
            logger.error(f"Failed to get compliance trends: {e}")
            return {"error": str(e)}
    
    async def _get_risk_distribution(self) -> Dict[str, Any]:
        """Get risk assessment distribution data"""
        try:
            performance_metrics = self.metrics_collector.get_performance_metrics()
            risk_dist = performance_metrics.get("risk_score_distribution", {})
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "distribution": {
                    "low_risk": risk_dist.get("low_risk_count", 0),
                    "medium_risk": risk_dist.get("medium_risk_count", 0),
                    "high_risk": risk_dist.get("high_risk_count", 0)
                },
                "statistics": {
                    "average_risk": risk_dist.get("avg", 0.0),
                    "median_risk": risk_dist.get("median", 0.0),
                    "total_assessments": sum([
                        risk_dist.get("low_risk_count", 0),
                        risk_dist.get("medium_risk_count", 0),
                        risk_dist.get("high_risk_count", 0)
                    ])
                }
            }
        except Exception as e:
            logger.error(f"Failed to get risk distribution: {e}")
            return {"error": str(e)}
    
    async def _broadcast_metrics(self):
        """Broadcast metrics to connected WebSocket clients"""
        while True:
            try:
                if self.active_connections:
                    # Get current metrics
                    performance = self.metrics_collector.get_performance_metrics()
                    security = self.metrics_collector.get_security_metrics()
                    
                    message = json.dumps({
                        "type": "metrics_update",
                        "performance": performance,
                        "security": security,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Send to all connected clients
                    disconnected = []
                    for connection in self.active_connections:
                        try:
                            await connection.send_text(message)
                        except Exception:
                            disconnected.append(connection)
                    
                    # Remove disconnected clients
                    for conn in disconnected:
                        self.active_connections.remove(conn)
                
                await asyncio.sleep(5)  # Broadcast every 5 seconds
                
            except Exception as e:
                logger.error(f"Metrics broadcast failed: {e}")
                await asyncio.sleep(10)
    
    async def _check_alerts(self):
        """Periodically check for alerts and trigger notifications"""
        while True:
            try:
                alerts = self.metrics_collector.check_alerts()
                
                # Log critical alerts
                for alert in alerts:
                    if alert["severity"] == "critical":
                        logger.critical(f"🚨 CRITICAL ALERT: {alert['message']}")
                    elif alert["severity"] == "error":
                        logger.error(f"🔥 ERROR ALERT: {alert['message']}")
                    elif alert["severity"] == "warning":
                        logger.warning(f"⚠️ WARNING ALERT: {alert['message']}")
                
                await asyncio.sleep(30)  # Check alerts every 30 seconds
                
            except Exception as e:
                logger.error(f"Alert checking failed: {e}")
                await asyncio.sleep(60)
    
    async def start_background_tasks(self):
        """Start background tasks when event loop is available"""
        if not self._background_tasks_started:
            asyncio.create_task(self._broadcast_metrics())
            asyncio.create_task(self._check_alerts())
            self._background_tasks_started = True
            logger.info("🔄 Background tasks started")
    
    def start(self):
        """Start the dashboard server"""
        logger.info(f"🚀 Starting Guardial Security Dashboard on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")


# Singleton instance
_dashboard = None

def get_security_dashboard(host: str = "0.0.0.0", port: int = 8080) -> SecurityDashboard:
    """Get singleton security dashboard"""
    global _dashboard
    if _dashboard is None:
        _dashboard = SecurityDashboard(host, port)
    return _dashboard

def start_dashboard_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the security dashboard server"""
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        dashboard = get_security_dashboard(host, port)
        
        # Start background tasks in the event loop
        loop.run_until_complete(dashboard.start_background_tasks())
        
        # Start the server
        dashboard.start()
    except Exception as e:
        logger.error(f"Failed to start dashboard server: {e}")
    finally:
        loop.close()