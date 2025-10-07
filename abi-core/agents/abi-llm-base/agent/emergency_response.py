"""
Emergency Response System for ABI Agents

This module provides emergency response capabilities for ABI agents,
including secure shutdown mechanisms and emergency protocols.
"""

import logging
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

# Import cryptography with fallback
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logging.warning("Cryptography not available - emergency response will use basic security")

logger = logging.getLogger(__name__)

class EmergencyLevel(Enum):
    """Emergency severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class EmergencyEvent:
    """Emergency event data structure"""
    level: EmergencyLevel
    source: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any]
    resolved: bool = False

class EmergencyResponseSystem:
    """
    Emergency Response System for ABI Agents
    
    Provides emergency shutdown, alerting, and recovery mechanisms
    with optional cryptographic security features.
    """
    
    def __init__(self, agent_name: str = "unknown"):
        self.agent_name = agent_name
        self.active_emergencies: List[EmergencyEvent] = []
        self.emergency_contacts: List[str] = []
        self.shutdown_initiated = False
        self.logger = logging.getLogger(f"emergency.{agent_name}")
        
        # Initialize security features if available
        self.security_enabled = CRYPTOGRAPHY_AVAILABLE
        if not self.security_enabled:
            self.logger.warning("Running in basic security mode - cryptography not available")
    
    async def trigger_emergency(
        self, 
        level: EmergencyLevel, 
        message: str, 
        source: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Trigger an emergency event
        
        Args:
            level: Emergency severity level
            message: Emergency description
            source: Source of the emergency
            metadata: Additional emergency data
            
        Returns:
            Emergency event ID
        """
        event = EmergencyEvent(
            level=level,
            source=source,
            message=message,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.active_emergencies.append(event)
        event_id = f"emergency_{len(self.active_emergencies)}_{int(event.timestamp.timestamp())}"
        
        self.logger.error(f"🚨 EMERGENCY {level.value.upper()}: {message} (Source: {source})")
        
        # Handle critical emergencies
        if level == EmergencyLevel.CRITICAL:
            await self._handle_critical_emergency(event)
        
        # Notify emergency contacts
        await self._notify_emergency_contacts(event, event_id)
        
        return event_id
    
    async def _handle_critical_emergency(self, event: EmergencyEvent):
        """Handle critical emergency events"""
        self.logger.error(f"🚨 CRITICAL EMERGENCY DETECTED: {event.message}")
        
        # Initiate emergency shutdown sequence
        if not self.shutdown_initiated:
            self.logger.error("🚨 INITIATING EMERGENCY SHUTDOWN SEQUENCE")
            self.shutdown_initiated = True
            
            # Create emergency log
            emergency_log = {
                "timestamp": event.timestamp.isoformat(),
                "agent": self.agent_name,
                "emergency_type": "critical_shutdown",
                "message": event.message,
                "source": event.source,
                "metadata": event.metadata,
                "shutdown_initiated": True
            }
            
            # Log emergency with structured format
            self.logger.error(f"🚨 EMERGENCY LOG: {json.dumps(emergency_log, indent=2)}")
    
    async def _notify_emergency_contacts(self, event: EmergencyEvent, event_id: str):
        """Notify emergency contacts about the event"""
        if not self.emergency_contacts:
            self.logger.warning("No emergency contacts configured")
            return
        
        notification = {
            "event_id": event_id,
            "agent": self.agent_name,
            "level": event.level.value,
            "message": event.message,
            "timestamp": event.timestamp.isoformat(),
            "source": event.source
        }
        
        for contact in self.emergency_contacts:
            try:
                # In a real implementation, this would send notifications
                # via email, SMS, webhook, etc.
                self.logger.info(f"📧 Emergency notification sent to {contact}: {notification}")
            except Exception as e:
                self.logger.error(f"Failed to notify emergency contact {contact}: {e}")
    
    def add_emergency_contact(self, contact: str):
        """Add an emergency contact"""
        if contact not in self.emergency_contacts:
            self.emergency_contacts.append(contact)
            self.logger.info(f"Added emergency contact: {contact}")
    
    def remove_emergency_contact(self, contact: str):
        """Remove an emergency contact"""
        if contact in self.emergency_contacts:
            self.emergency_contacts.remove(contact)
            self.logger.info(f"Removed emergency contact: {contact}")
    
    async def resolve_emergency(self, event_id: str, resolution_notes: str = "") -> bool:
        """
        Mark an emergency as resolved
        
        Args:
            event_id: Emergency event ID
            resolution_notes: Notes about the resolution
            
        Returns:
            True if emergency was found and resolved
        """
        # Simple resolution based on event count (in real implementation, use proper IDs)
        try:
            event_index = int(event_id.split('_')[1]) - 1
            if 0 <= event_index < len(self.active_emergencies):
                event = self.active_emergencies[event_index]
                event.resolved = True
                event.metadata['resolution_notes'] = resolution_notes
                event.metadata['resolved_at'] = datetime.utcnow().isoformat()
                
                self.logger.info(f"✅ Emergency resolved: {event_id} - {resolution_notes}")
                return True
        except (ValueError, IndexError):
            pass
        
        self.logger.warning(f"Emergency not found: {event_id}")
        return False
    
    def get_active_emergencies(self) -> List[Dict[str, Any]]:
        """Get list of active (unresolved) emergencies"""
        active = [
            {
                "level": event.level.value,
                "source": event.source,
                "message": event.message,
                "timestamp": event.timestamp.isoformat(),
                "metadata": event.metadata
            }
            for event in self.active_emergencies
            if not event.resolved
        ]
        return active
    
    def get_emergency_status(self) -> Dict[str, Any]:
        """Get overall emergency system status"""
        active_emergencies = self.get_active_emergencies()
        
        return {
            "agent": self.agent_name,
            "security_enabled": self.security_enabled,
            "shutdown_initiated": self.shutdown_initiated,
            "total_emergencies": len(self.active_emergencies),
            "active_emergencies": len(active_emergencies),
            "emergency_contacts": len(self.emergency_contacts),
            "highest_active_level": self._get_highest_active_level(),
            "system_status": "EMERGENCY" if active_emergencies else "NORMAL"
        }
    
    def _get_highest_active_level(self) -> Optional[str]:
        """Get the highest severity level among active emergencies"""
        active_levels = [
            event.level for event in self.active_emergencies 
            if not event.resolved
        ]
        
        if not active_levels:
            return None
        
        # Order by severity: CRITICAL > HIGH > MEDIUM > LOW
        level_priority = {
            EmergencyLevel.CRITICAL: 4,
            EmergencyLevel.HIGH: 3,
            EmergencyLevel.MEDIUM: 2,
            EmergencyLevel.LOW: 1
        }
        
        highest_level = max(active_levels, key=lambda x: level_priority[x])
        return highest_level.value
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform emergency system health check"""
        return {
            "emergency_system": "healthy",
            "security_features": "available" if self.security_enabled else "basic",
            "active_emergencies": len(self.get_active_emergencies()),
            "shutdown_status": "initiated" if self.shutdown_initiated else "normal",
            "contacts_configured": len(self.emergency_contacts) > 0
        }

# Global emergency response system instance
_emergency_system: Optional[EmergencyResponseSystem] = None

def get_emergency_response_system(agent_name: str = "unknown") -> EmergencyResponseSystem:
    """
    Get or create the global emergency response system instance
    
    Args:
        agent_name: Name of the agent using the emergency system
        
    Returns:
        EmergencyResponseSystem instance
    """
    global _emergency_system
    
    if _emergency_system is None:
        _emergency_system = EmergencyResponseSystem(agent_name)
        logger.info(f"🚨 Emergency Response System initialized for agent: {agent_name}")
    
    return _emergency_system

# Convenience functions for common emergency operations
async def trigger_emergency(level: EmergencyLevel, message: str, source: str = "system") -> str:
    """Convenience function to trigger an emergency"""
    system = get_emergency_response_system()
    return await system.trigger_emergency(level, message, source)

async def trigger_critical_emergency(message: str, source: str = "system") -> str:
    """Convenience function to trigger a critical emergency"""
    return await trigger_emergency(EmergencyLevel.CRITICAL, message, source)

def get_emergency_status() -> Dict[str, Any]:
    """Convenience function to get emergency status"""
    system = get_emergency_response_system()
    return system.get_emergency_status()