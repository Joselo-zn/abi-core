#!/usr/bin/env python3
"""
CLI Reporter for Observer Agent
Usage: python cli_reporter.py [command] [options]
"""
import asyncio
import json
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
from rich.text import Text

console = Console()

class ObserverCLI:
    """Command-line interface for Observer reports"""
    
    def __init__(self, observer_url: str = "http://localhost:11439"):
        self.observer_url = observer_url.rstrip('/')
    
    def get_data(self, endpoint: str) -> Dict[str, Any]:
        """Fetch data from Observer API"""
        try:
            response = requests.get(f"{self.observer_url}/api/{endpoint}", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Error connecting to Observer: {e}[/red]")
            return {}
    
    def show_health(self):
        """Display system health report"""
        console.print("\n[bold blue]🏥 SYSTEM HEALTH REPORT[/bold blue]")
        
        health_data = self.get_data("health")
        if not health_data:
            return
        
        health_score = health_data.get('health_score', 0) * 100
        
        # Health score with color coding
        if health_score >= 80:
            score_color = "green"
            status = "HEALTHY"
        elif health_score >= 60:
            score_color = "yellow"
            status = "WARNING"
        else:
            score_color = "red"
            status = "CRITICAL"
        
        console.print(Panel(
            f"[{score_color}]{health_score:.1f}% - {status}[/{score_color}]",
            title="Health Score",
            border_style=score_color
        ))
        
        # System metrics
        if 'metrics' in health_data and 'system_metrics' in health_data['metrics']:
            metrics = health_data['metrics']['system_metrics']
            
            table = Table(title="System Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Total Tasks", str(metrics.get('total_tasks', 0)))
            table.add_row("Completed Tasks", str(metrics.get('completed_tasks', 0)))
            table.add_row("Failed Tasks", str(metrics.get('failed_tasks', 0)))
            table.add_row("Error Rate", f"{metrics.get('error_rate', 0) * 100:.2f}%")
            table.add_row("Active Agents", str(len(metrics.get('active_agents', []))))
            
            console.print(table)
        
        # LLM Analysis
        if 'analysis' in health_data:
            console.print(Panel(
                health_data['analysis'],
                title="AI Analysis",
                border_style="blue"
            ))
    
    def show_anomalies(self):
        """Display detected anomalies"""
        console.print("\n[bold red]🚨 ANOMALY DETECTION REPORT[/bold red]")
        
        anomalies_data = self.get_data("anomalies")
        if not anomalies_data:
            return
        
        anomalies = anomalies_data.get('anomalies', [])
        
        if not anomalies:
            console.print("[green]✅ No anomalies detected - System operating normally[/green]")
            return
        
        for i, anomaly in enumerate(anomalies, 1):
            severity_color = {
                'high': 'red',
                'medium': 'yellow',
                'low': 'blue'
            }.get(anomaly.get('severity', 'low'), 'white')
            
            console.print(Panel(
                f"[bold]{anomaly.get('description', 'Unknown anomaly')}[/bold]\n"
                f"Type: {anomaly.get('type', 'unknown')}\n"
                f"Confidence: {anomaly.get('confidence', 0) * 100:.1f}%",
                title=f"Anomaly #{i} - {anomaly.get('severity', 'unknown').upper()}",
                border_style=severity_color
            ))
    
    def show_performance(self):
        """Display agent performance metrics"""
        console.print("\n[bold green]⚡ AGENT PERFORMANCE REPORT[/bold green]")
        
        perf_data = self.get_data("performance")
        if not perf_data:
            return
        
        performance = perf_data.get('performance', {})
        
        if not performance:
            console.print("[yellow]No performance data available[/yellow]")
            return
        
        table = Table(title="Agent Performance Metrics")
        table.add_column("Agent", style="cyan")
        table.add_column("Tasks", justify="right")
        table.add_column("Success Rate", justify="right")
        table.add_column("Avg Response", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Status", justify="center")
        
        for agent_name, metrics in performance.items():
            success_rate = metrics.get('success_rate', 0)
            
            # Status indicator
            if metrics.get('last_activity'):
                last_activity = datetime.fromisoformat(metrics['last_activity'].replace('Z', '+00:00'))
                if datetime.now().replace(tzinfo=last_activity.tzinfo) - last_activity < timedelta(minutes=5):
                    status = "[green]🟢 Active[/green]"
                elif datetime.now().replace(tzinfo=last_activity.tzinfo) - last_activity < timedelta(minutes=15):
                    status = "[yellow]🟡 Idle[/yellow]"
                else:
                    status = "[red]🔴 Inactive[/red]"
            else:
                status = "[gray]⚫ Unknown[/gray]"
            
            # Success rate color
            if success_rate >= 90:
                success_color = "green"
            elif success_rate >= 70:
                success_color = "yellow"
            else:
                success_color = "red"
            
            table.add_row(
                agent_name,
                str(metrics.get('task_count', 0)),
                f"[{success_color}]{success_rate:.1f}%[/{success_color}]",
                f"{metrics.get('average_response_time', 0):.2f}s",
                str(metrics.get('error_count', 0)),
                status
            )
        
        console.print(table)
    
    def show_events(self, hours: int = 1):
        """Display recent events"""
        console.print(f"\n[bold cyan]📊 RECENT EVENTS (Last {hours}h)[/bold cyan]")
        
        events_data = self.get_data(f"events?hours={hours}")
        if not events_data:
            return
        
        events = events_data.get('events', [])
        
        if not events:
            console.print("[yellow]No recent events found[/yellow]")
            return
        
        table = Table(title=f"Events from last {hours} hour(s)")
        table.add_column("Time", style="dim")
        table.add_column("Event Type", style="cyan")
        table.add_column("Agent", style="magenta")
        table.add_column("Content", style="white")
        
        for event in events[-20:]:  # Show last 20 events
            timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            time_str = timestamp.strftime("%H:%M:%S")
            
            table.add_row(
                time_str,
                event.get('event_type', 'unknown'),
                event.get('agent_name', 'unknown'),
                event.get('content', '')[:50] + "..." if len(event.get('content', '')) > 50 else event.get('content', '')
            )
        
        console.print(table)
    
    def show_full_report(self):
        """Display comprehensive report"""
        console.print("\n[bold magenta]📋 COMPREHENSIVE OBSERVATION REPORT[/bold magenta]")
        
        report_data = self.get_data("report")
        if not report_data:
            return
        
        # Report header
        console.print(Panel(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Window: {report_data.get('observation_window_minutes', 30)} minutes",
            title="Report Info"
        ))
        
        # Quick summary
        event_summary = report_data.get('event_summary', {})
        console.print(Panel(
            f"Total Events: {event_summary.get('total_events', 0)}\n"
            f"Active Agents: {len(event_summary.get('active_agents', []))}\n"
            f"Active Contexts: {event_summary.get('active_contexts', 0)}",
            title="Summary"
        ))
        
        # Recommendations
        recommendations = report_data.get('recommendations', [])
        if recommendations:
            console.print("\n[bold yellow]💡 RECOMMENDATIONS[/bold yellow]")
            for i, rec in enumerate(recommendations, 1):
                console.print(f"{i}. {rec}")
    
    def monitor_live(self, interval: int = 30):
        """Live monitoring mode"""
        console.print(f"[bold green]🔴 LIVE MONITORING (Updates every {interval}s)[/bold green]")
        console.print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                console.clear()
                console.print(f"[dim]Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n")
                
                # Quick health check
                health_data = self.get_data("health")
                if health_data:
                    health_score = health_data.get('health_score', 0) * 100
                    if health_score >= 80:
                        console.print(f"[green]🟢 System Health: {health_score:.1f}%[/green]")
                    elif health_score >= 60:
                        console.print(f"[yellow]🟡 System Health: {health_score:.1f}%[/yellow]")
                    else:
                        console.print(f"[red]🔴 System Health: {health_score:.1f}%[/red]")
                
                # Quick anomaly check
                anomalies_data = self.get_data("anomalies")
                if anomalies_data:
                    anomaly_count = len(anomalies_data.get('anomalies', []))
                    if anomaly_count > 0:
                        console.print(f"[red]⚠️  {anomaly_count} anomalies detected[/red]")
                    else:
                        console.print("[green]✅ No anomalies[/green]")
                
                console.print(f"\n[dim]Next update in {interval} seconds...[/dim]")
                
                import time
                time.sleep(interval)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped[/yellow]")

def main():
    parser = argparse.ArgumentParser(description="ABI Observer CLI Reporter")
    parser.add_argument("--url", default="http://localhost:11439", help="Observer service URL")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Health command
    subparsers.add_parser("health", help="Show system health report")
    
    # Anomalies command
    subparsers.add_parser("anomalies", help="Show detected anomalies")
    
    # Performance command
    subparsers.add_parser("performance", help="Show agent performance metrics")
    
    # Events command
    events_parser = subparsers.add_parser("events", help="Show recent events")
    events_parser.add_argument("--hours", type=int, default=1, help="Hours of history to show")
    
    # Report command
    subparsers.add_parser("report", help="Show comprehensive report")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Live monitoring mode")
    monitor_parser.add_argument("--interval", type=int, default=30, help="Update interval in seconds")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = ObserverCLI(args.url)
    
    if args.command == "health":
        cli.show_health()
    elif args.command == "anomalies":
        cli.show_anomalies()
    elif args.command == "performance":
        cli.show_performance()
    elif args.command == "events":
        cli.show_events(args.hours)
    elif args.command == "report":
        cli.show_full_report()
    elif args.command == "monitor":
        cli.monitor_live(args.interval)

if __name__ == "__main__":
    main()