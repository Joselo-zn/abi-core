import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncIterable
from dataclasses import dataclass, asdict

from a2a.types import (
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
from common import prompts
from agent.agent import AbiAgent

from langchain_community.chat_models import ChatOllama
from langchain.schema.messages import HumanMessage
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv('MODEL_NAME', 'tinyllama:latest')

@dataclass
class ObservationEvent:
    """Represents a single observation event"""
    timestamp: datetime
    event_type: str
    agent_name: str
    task_id: str
    context_id: str
    content: str
    metadata: Dict[str, Any]
    confidence: float = 1.0

@dataclass
class SystemMetrics:
    """System-wide metrics collected by observer"""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_latency: float = 0.0
    active_agents: List[str] = None
    error_rate: float = 0.0
    
    def __post_init__(self):
        if self.active_agents is None:
            self.active_agents = []

@dataclass
class AgentPerformance:
    """Performance metrics for individual agents"""
    agent_name: str
    task_count: int = 0
    success_rate: float = 0.0
    average_response_time: float = 0.0
    last_activity: Optional[datetime] = None
    error_count: int = 0

class AbiObserverAgent(AbiAgent):
    """Observer Agent for monitoring system activity and agent interactions."""

    def __init__(self):
        super().__init__(
            agent_name='Abi Observer Agent',
            description='Monitor and analyze agent interactions and system performance',
            content_types=['text', 'text/plain', 'application/json'],
        )
        
        # Initialize LLM for analysis
        self.llm = ChatOllama(model_name=MODEL_NAME, temperature=0.0)
        
        # Observation storage
        self.events: deque = deque(maxlen=1000)  # Keep last 1000 events
        self.agent_metrics: Dict[str, AgentPerformance] = {}
        self.system_metrics = SystemMetrics()
        
        # Tracking state
        self.task_start_times: Dict[str, datetime] = {}
        self.agent_interactions: Dict[str, List[str]] = defaultdict(list)
        self.anomaly_patterns: List[Dict[str, Any]] = []
        
        # Configuration
        self.observation_window = timedelta(minutes=30)  # Analysis window
        self.anomaly_threshold = 0.7  # Confidence threshold for anomalies
        
        # Initialize REST API
        self.api_app = self._setup_api()
        
        logger.info(f'[👁️] Starting ABI Observer Agent')

    def record_event(self, event_type: str, agent_name: str, task_id: str, 
                    context_id: str, content: str, metadata: Dict[str, Any] = None):
        """Record a new observation event"""
        event = ObservationEvent(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            agent_name=agent_name,
            task_id=task_id,
            context_id=context_id,
            content=content,
            metadata=metadata or {}
        )
        
        self.events.append(event)
        self._update_metrics(event)
        logger.debug(f"[👁️] Recorded event: {event_type} from {agent_name}")

    def _update_metrics(self, event: ObservationEvent):
        """Update system and agent metrics based on new event"""
        agent_name = event.agent_name
        
        # Initialize agent metrics if not exists
        if agent_name not in self.agent_metrics:
            self.agent_metrics[agent_name] = AgentPerformance(agent_name=agent_name)
        
        agent_perf = self.agent_metrics[agent_name]
        agent_perf.last_activity = event.timestamp
        
        # Update based on event type
        if event.event_type == 'task_started':
            self.task_start_times[event.task_id] = event.timestamp
            self.system_metrics.total_tasks += 1
            agent_perf.task_count += 1
            
        elif event.event_type == 'task_completed':
            if event.task_id in self.task_start_times:
                duration = (event.timestamp - self.task_start_times[event.task_id]).total_seconds()
                agent_perf.average_response_time = (
                    (agent_perf.average_response_time * (agent_perf.task_count - 1) + duration) 
                    / agent_perf.task_count
                )
                del self.task_start_times[event.task_id]
            
            self.system_metrics.completed_tasks += 1
            
        elif event.event_type == 'task_failed':
            self.system_metrics.failed_tasks += 1
            agent_perf.error_count += 1
        
        # Update success rate
        if agent_perf.task_count > 0:
            agent_perf.success_rate = 1.0 - (agent_perf.error_count / agent_perf.task_count)
        
        # Update system error rate
        if self.system_metrics.total_tasks > 0:
            self.system_metrics.error_rate = (
                self.system_metrics.failed_tasks / self.system_metrics.total_tasks
            )

    def get_recent_events(self, window: timedelta = None) -> List[ObservationEvent]:
        """Get events within the specified time window"""
        if window is None:
            window = self.observation_window
            
        cutoff_time = datetime.utcnow() - window
        return [event for event in self.events if event.timestamp >= cutoff_time]

    async def analyze_system_health(self) -> Dict[str, Any]:
        """Analyze overall system health and performance"""
        recent_events = self.get_recent_events()
        
        analysis_data = {
            'total_events': len(recent_events),
            'system_metrics': asdict(self.system_metrics),
            'agent_performance': {name: asdict(perf) for name, perf in self.agent_metrics.items()},
            'recent_activity': len([e for e in recent_events if e.timestamp >= datetime.utcnow() - timedelta(minutes=5)])
        }
        
        # Use LLM to analyze the data
        prompt = prompts.OBSERVER_COT_INSTRUCTIONS.replace(
            '{observation_data}', json.dumps(analysis_data, indent=2, default=str)
        )
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            analysis_result = {
                'health_score': self._calculate_health_score(),
                'analysis': response.content,
                'metrics': analysis_data,
                'timestamp': datetime.utcnow().isoformat(),
                'anomalies_detected': len(self.anomaly_patterns)
            }
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in system health analysis: {e}")
            return {
                'health_score': 0.5,
                'analysis': f"Analysis failed: {str(e)}",
                'metrics': analysis_data,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }

    def _calculate_health_score(self) -> float:
        """Calculate a health score based on system metrics"""
        score = 1.0
        
        # Penalize high error rate
        if self.system_metrics.error_rate > 0.1:  # More than 10% errors
            score -= 0.3
        elif self.system_metrics.error_rate > 0.05:  # More than 5% errors
            score -= 0.1
        
        # Penalize inactive agents
        active_agents = len([perf for perf in self.agent_metrics.values() 
                           if perf.last_activity and 
                           perf.last_activity >= datetime.utcnow() - timedelta(minutes=10)])
        
        if active_agents < 3:  # Expect at least orchestrator, planner, actor
            score -= 0.2
        
        # Penalize slow response times
        avg_response_times = [perf.average_response_time for perf in self.agent_metrics.values() 
                             if perf.average_response_time > 0]
        if avg_response_times:
            avg_system_response = sum(avg_response_times) / len(avg_response_times)
            if avg_system_response > 30:  # More than 30 seconds average
                score -= 0.2
            elif avg_system_response > 10:  # More than 10 seconds average
                score -= 0.1
        
        return max(0.0, min(1.0, score))

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalous patterns in recent events"""
        recent_events = self.get_recent_events()
        anomalies = []
        
        # Check for repeated failures
        failure_events = [e for e in recent_events if e.event_type == 'task_failed']
        if len(failure_events) > 3:  # More than 3 failures in window
            anomalies.append({
                'type': 'high_failure_rate',
                'severity': 'high',
                'description': f'Detected {len(failure_events)} task failures in recent activity',
                'events': len(failure_events),
                'confidence': 0.9
            })
        
        # Check for agent inactivity
        for agent_name, perf in self.agent_metrics.items():
            if perf.last_activity and perf.last_activity < datetime.utcnow() - timedelta(minutes=15):
                anomalies.append({
                    'type': 'agent_inactive',
                    'severity': 'medium',
                    'description': f'Agent {agent_name} has been inactive for >15 minutes',
                    'agent': agent_name,
                    'last_seen': perf.last_activity.isoformat(),
                    'confidence': 0.8
                })
        
        # Check for performance degradation
        for agent_name, perf in self.agent_metrics.items():
            if perf.success_rate < 0.7 and perf.task_count > 5:  # Less than 70% success rate
                anomalies.append({
                    'type': 'performance_degradation',
                    'severity': 'medium',
                    'description': f'Agent {agent_name} has low success rate: {perf.success_rate:.2%}',
                    'agent': agent_name,
                    'success_rate': perf.success_rate,
                    'confidence': 0.8
                })
        
        return anomalies

    async def generate_observation_report(self) -> Dict[str, Any]:
        """Generate a comprehensive observation report"""
        health_analysis = await self.analyze_system_health()
        anomalies = self.detect_anomalies()
        recent_events = self.get_recent_events()
        
        report = {
            'report_type': 'system_observation',
            'timestamp': datetime.utcnow().isoformat(),
            'observation_window_minutes': int(self.observation_window.total_seconds() / 60),
            'health_analysis': health_analysis,
            'anomalies': anomalies,
            'event_summary': {
                'total_events': len(recent_events),
                'event_types': dict(defaultdict(int, 
                    [(event.event_type, len([e for e in recent_events if e.event_type == event.event_type])) 
                     for event in recent_events])),
                'active_agents': list(self.agent_metrics.keys()),
                'active_contexts': len(set(event.context_id for event in recent_events))
            },
            'recommendations': self._generate_recommendations(anomalies, health_analysis)
        }
        
        return report

    def _generate_recommendations(self, anomalies: List[Dict], health_analysis: Dict) -> List[str]:
        """Generate actionable recommendations based on observations"""
        recommendations = []
        
        health_score = health_analysis.get('health_score', 0.5)
        
        if health_score < 0.7:
            recommendations.append("System health is below optimal. Consider investigating recent changes.")
        
        for anomaly in anomalies:
            if anomaly['type'] == 'high_failure_rate':
                recommendations.append("High failure rate detected. Check agent logs and error patterns.")
            elif anomaly['type'] == 'agent_inactive':
                recommendations.append(f"Agent {anomaly['agent']} appears inactive. Verify agent health.")
            elif anomaly['type'] == 'performance_degradation':
                recommendations.append(f"Performance issues with {anomaly['agent']}. Consider resource allocation.")
        
        if self.system_metrics.error_rate > 0.1:
            recommendations.append("Error rate is high. Review system configuration and policies.")
        
        if not recommendations:
            recommendations.append("System operating normally. Continue monitoring.")
        
        return recommendations

    def _setup_api(self) -> FastAPI:
        """Setup REST API for external access"""
        app = FastAPI(title="ABI Observer API", version="1.0.0")
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Root endpoint
        @app.get("/")
        async def root():
            """Root endpoint"""
            return {"message": "ABI Observer API", "status": "running", "endpoints": ["/api/health", "/api/anomalies", "/api/performance", "/api/events", "/api/report", "/metrics"]}
        
        @app.get("/api/health")
        async def get_health():
            return await self.analyze_system_health()
        
        @app.get("/api/anomalies")
        async def get_anomalies():
            return {"anomalies": self.detect_anomalies()}
        
        @app.get("/api/events")
        async def get_events(hours: int = 1):
            window = timedelta(hours=hours)
            events = self.get_recent_events(window)
            return {
                "events": [
                    {
                        "timestamp": event.timestamp.isoformat(),
                        "event_type": event.event_type,
                        "agent_name": event.agent_name,
                        "task_id": event.task_id,
                        "context_id": event.context_id,
                        "content": event.content,
                        "metadata": event.metadata
                    }
                    for event in events
                ]
            }
        
        @app.get("/api/performance")
        async def get_performance():
            return {
                "performance": {
                    name: {
                        "agent_name": perf.agent_name,
                        "task_count": perf.task_count,
                        "success_rate": perf.success_rate,
                        "average_response_time": perf.average_response_time,
                        "last_activity": perf.last_activity.isoformat() if perf.last_activity else None,
                        "error_count": perf.error_count
                    }
                    for name, perf in self.agent_metrics.items()
                }
            }
        
        @app.get("/api/report")
        async def get_report():
            return await self.generate_observation_report()
        
        @app.get("/api/metrics/system")
        async def get_system_metrics():
            return {
                "total_tasks": self.system_metrics.total_tasks,
                "completed_tasks": self.system_metrics.completed_tasks,
                "failed_tasks": self.system_metrics.failed_tasks,
                "error_rate": self.system_metrics.error_rate,
                "active_agents": self.system_metrics.active_agents,
                "health_score": self._calculate_health_score()
            }
        
        @app.get("/metrics")
        async def prometheus_metrics():
            """Prometheus metrics endpoint"""
            metrics = []
            
            # System metrics
            metrics.append(f'abi_system_health_score {self._calculate_health_score()}')
            metrics.append(f'abi_total_tasks {self.system_metrics.total_tasks}')
            metrics.append(f'abi_completed_tasks {self.system_metrics.completed_tasks}')
            metrics.append(f'abi_failed_tasks {self.system_metrics.failed_tasks}')
            metrics.append(f'abi_error_rate {self.system_metrics.error_rate}')
            metrics.append(f'abi_active_agents {len(self.agent_metrics)}')
            
            # Agent metrics
            for agent_name, perf in self.agent_metrics.items():
                agent_label = agent_name.replace('-', '_').replace(' ', '_').lower()
                metrics.append(f'abi_agent_success_rate{{agent="{agent_name}"}} {perf.success_rate}')
                metrics.append(f'abi_agent_task_count{{agent="{agent_name}"}} {perf.task_count}')
                metrics.append(f'abi_agent_response_time{{agent="{agent_name}"}} {perf.average_response_time}')
                metrics.append(f'abi_agent_error_count{{agent="{agent_name}"}} {perf.error_count}')
            
            # Anomalies
            anomalies = self.detect_anomalies()
            metrics.append(f'abi_anomalies_total {len(anomalies)}')
            
            for severity in ['high', 'medium', 'low']:
                count = len([a for a in anomalies if a.get('severity') == severity])
                metrics.append(f'abi_anomalies_by_severity{{severity="{severity}"}} {count}')
            
            return "\n".join(metrics)
        
        return app

    async def start_api_server(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the REST API server"""
        config = uvicorn.Config(
            app=self.api_app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        logger.info(f"🌐 Observer API starting on http://{host}:{port}")
        await server.serve()

    async def stream(self, query: str, context_id: str, task_id: str) -> AsyncIterable[dict]:
        """Main streaming interface for the Observer Agent"""
        logger.info(f'[👁️] Observer Agent processing request: {query}')
        
        # Record the observation request
        self.record_event('observation_request', 'observer', task_id, context_id, query)
        
        try:
            # Generate observation report
            yield {
                'response_type': 'text',
                'is_task_complete': False,
                'require_user_input': False,
                'content': '🔍 Analyzing system activity and generating observation report...'
            }
            
            report = await self.generate_observation_report()
            
            # Record completion
            self.record_event('observation_completed', 'observer', task_id, context_id, 
                            f"Generated report with {len(report.get('anomalies', []))} anomalies")
            
            yield {
                'response_type': 'data',
                'is_task_complete': True,
                'require_user_input': False,
                'content': report
            }
            
        except Exception as e:
            logger.error(f"Error in observer stream: {e}")
            self.record_event('observation_failed', 'observer', task_id, context_id, str(e))
            
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': f'❌ Observation failed: {str(e)}'
            }

    def process_agent_event(self, agent_name: str, event_type: str, task_id: str, 
                          context_id: str, content: str, metadata: Dict[str, Any] = None):
        """Process events from other agents for observation"""
        self.record_event(event_type, agent_name, task_id, context_id, content, metadata)
        
        # Check for immediate anomalies
        if event_type == 'task_failed':
            recent_failures = len([e for e in self.get_recent_events(timedelta(minutes=5)) 
                                 if e.event_type == 'task_failed'])
            if recent_failures >= 3:
                logger.warning(f"[👁️] Anomaly detected: {recent_failures} failures in 5 minutes")
