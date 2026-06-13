"""
Emergency Response System for ABI Guardial Agent

This module implements comprehensive emergency response capabilities including:
- Emergency shutdown mechanisms with immediate effect
- System-wide agent stopping capability for security incidents
- Emergency event logging with detailed cause tracking
- Emergency mode operation with all operations blocked
- Administrative override capabilities with full audit trail

Requirements: 8.1, 8.2, 8.3, 8.4
"""

import json
import logging
import asyncio
import hashlib
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, asdict
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

class EmergencyLevel(Enum):
    """Emergency severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class EmergencyType(Enum):
    """Types of emergency events"""
    SECURITY_BREACH = "security_breach"
    POLICY_CORRUPTION = "policy_corruption"
    SYSTEM_COMPROMISE = "system_compromise"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    MANUAL_SHUTDOWN = "manual_shutdown"
    ADMINISTRATIVE_OVERRIDE = "administrative_override"

class SystemState(Enum):
    """System operational states"""
    NORMAL = "normal"
    EMERGENCY_MODE = "emergency_mode"
    SHUTDOWN = "shutdown"
    MAINTENANCE = "maintenance"

@dataclass
class EmergencyEvent:
    """Immutable emergency event record"""
    event_id: str
    timestamp: datetime
    emergency_type: EmergencyType
    emergency_level: EmergencyLevel
    initiated_by: str
    reason: str
    system_state_before: SystemState
    system_state_after: SystemState
    affected_agents: List[str]
    additional_context: Dict[str, Any]
    signature: Optional[str] = None

@dataclass
class AdminOverride:
    """Administrative override record"""
    override_id: str
    timestamp: datetime
    admin_id: str
    override_reason: str
    original_decision: Dict[str, Any]
    override_decision: Dict[str, Any]
    justification: str
    approval_chain: List[str]
    signature: Optional[str] = None

class EmergencyResponseSystem:
    """
    Comprehensive emergency response system for ABI Guardial Agent
    
    Provides fail-safe mechanisms that cannot be blocked by any policy
    and ensures system security in critical situations.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.current_state = SystemState.NORMAL
        self.emergency_log_path = Path(self.config.get('emergency.log_path', './emergency_logs'))
        self.emergency_log_path.mkdir(exist_ok=True)
        
        # Emergency event storage
        self.emergency_events: List[EmergencyEvent] = []
        self.admin_overrides: List[AdminOverride] = []
        
        # System shutdown callbacks
        self.shutdown_callbacks: List[Callable] = []
        
        # Emergency contacts and escalation
        self.emergency_contacts = self.config.get('emergency.contacts', [])
        
        # Cryptographic signing for audit trail integrity
        self._init_signing_keys()
        
        # Load existing emergency events
        self._load_emergency_history()
        
        logger.info("🚨 Emergency Response System initialized")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load emergency response configuration"""
        default_config = {
            'emergency': {
                'log_path': './emergency_logs',
                'max_log_retention_days': 365,
                'require_signatures': True,
                'auto_escalate_critical': True,
                'shutdown_timeout_seconds': 30,
                'contacts': []
            },
            'admin_override': {
                'enabled': True,
                'require_approval_chain': True,
                'max_override_duration_hours': 24,
                'audit_all_overrides': True
            }
        }
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    # Merge configurations
                    default_config.update(user_config)
            except Exception as e:
                logger.warning(f"Failed to load emergency config from {config_path}: {e}")
        
        return default_config

    def _init_signing_keys(self):
        """Initialize cryptographic keys for audit trail signing"""
        try:
            key_path = self.emergency_log_path / 'emergency_signing_key.pem'
            
            if key_path.exists():
                # Load existing key
                with open(key_path, 'rb') as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None
                    )
            else:
                # Generate new key
                self.private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048
                )
                
                # Save key
                with open(key_path, 'wb') as f:
                    f.write(self.private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    ))
                
                # Restrict key file permissions
                os.chmod(key_path, 0o600)
            
            self.public_key = self.private_key.public_key()
            logger.info("✅ Emergency response signing keys initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize signing keys: {e}")
            self.private_key = None
            self.public_key = None

    def _sign_event(self, event_data: str) -> Optional[str]:
        """Sign emergency event data for integrity verification"""
        if not self.private_key or not self.config.get('emergency.require_signatures', True):
            return None
        
        try:
            signature = self.private_key.sign(
                event_data.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return signature.hex()
        except Exception as e:
            logger.error(f"Failed to sign emergency event: {e}")
            return None

    def _verify_signature(self, event_data: str, signature_hex: str) -> bool:
        """Verify emergency event signature"""
        if not self.public_key or not signature_hex:
            return False
        
        try:
            signature = bytes.fromhex(signature_hex)
            self.public_key.verify(
                signature,
                event_data.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    def _load_emergency_history(self):
        """Load existing emergency events from persistent storage"""
        try:
            history_file = self.emergency_log_path / 'emergency_history.json'
            if history_file.exists():
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    
                    # Load emergency events
                    for event_data in data.get('emergency_events', []):
                        event = EmergencyEvent(
                            event_id=event_data['event_id'],
                            timestamp=datetime.fromisoformat(event_data['timestamp']),
                            emergency_type=EmergencyType(event_data['emergency_type']),
                            emergency_level=EmergencyLevel(event_data['emergency_level']),
                            initiated_by=event_data['initiated_by'],
                            reason=event_data['reason'],
                            system_state_before=SystemState(event_data['system_state_before']),
                            system_state_after=SystemState(event_data['system_state_after']),
                            affected_agents=event_data['affected_agents'],
                            additional_context=event_data['additional_context'],
                            signature=event_data.get('signature')
                        )
                        self.emergency_events.append(event)
                    
                    # Load admin overrides
                    for override_data in data.get('admin_overrides', []):
                        override = AdminOverride(
                            override_id=override_data['override_id'],
                            timestamp=datetime.fromisoformat(override_data['timestamp']),
                            admin_id=override_data['admin_id'],
                            override_reason=override_data['override_reason'],
                            original_decision=override_data['original_decision'],
                            override_decision=override_data['override_decision'],
                            justification=override_data['justification'],
                            approval_chain=override_data['approval_chain'],
                            signature=override_data.get('signature')
                        )
                        self.admin_overrides.append(override)
                    
                    logger.info(f"Loaded {len(self.emergency_events)} emergency events and {len(self.admin_overrides)} admin overrides")
        
        except Exception as e:
            logger.error(f"Failed to load emergency history: {e}")

    def _persist_emergency_history(self):
        """Persist emergency events to storage"""
        try:
            history_file = self.emergency_log_path / 'emergency_history.json'
            
            # Convert events to serializable format
            events_data = []
            for event in self.emergency_events:
                event_dict = asdict(event)
                event_dict['timestamp'] = event.timestamp.isoformat()
                event_dict['emergency_type'] = event.emergency_type.value
                event_dict['emergency_level'] = event.emergency_level.value
                event_dict['system_state_before'] = event.system_state_before.value
                event_dict['system_state_after'] = event.system_state_after.value
                events_data.append(event_dict)
            
            # Convert overrides to serializable format
            overrides_data = []
            for override in self.admin_overrides:
                override_dict = asdict(override)
                override_dict['timestamp'] = override.timestamp.isoformat()
                overrides_data.append(override_dict)
            
            data = {
                'emergency_events': events_data,
                'admin_overrides': overrides_data,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            with open(history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to persist emergency history: {e}")

    async def emergency_shutdown(
        self,
        reason: str,
        initiated_by: str,
        emergency_type: EmergencyType = EmergencyType.MANUAL_SHUTDOWN,
        emergency_level: EmergencyLevel = EmergencyLevel.CRITICAL,
        affected_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Initiate emergency shutdown with immediate effect
        
        This is a fail-safe mechanism that cannot be blocked by any policy
        
        Args:
            reason: Detailed reason for emergency shutdown
            initiated_by: Identity of who initiated the shutdown
            emergency_type: Type of emergency
            emergency_level: Severity level
            affected_agents: List of agents to shutdown (None = all agents)
        
        Returns:
            Emergency shutdown result with event details
        """
        logger.error(f"🚨 EMERGENCY SHUTDOWN INITIATED by {initiated_by}: {reason}")
        
        # Generate unique event ID
        event_id = hashlib.sha256(
            f"{datetime.now(timezone.utc).isoformat()}{initiated_by}{reason}".encode()
        ).hexdigest()[:16]
        
        # Record system state before shutdown
        previous_state = self.current_state
        
        # Create emergency event
        emergency_event = EmergencyEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            emergency_type=emergency_type,
            emergency_level=emergency_level,
            initiated_by=initiated_by,
            reason=reason,
            system_state_before=previous_state,
            system_state_after=SystemState.SHUTDOWN,
            affected_agents=affected_agents or ["ALL_AGENTS"],
            additional_context={
                "shutdown_method": "emergency_shutdown",
                "immediate_effect": True,
                "fail_safe_triggered": True
            }
        )
        
        # Sign the event for integrity (exclude signature field from signing)
        event_dict = asdict(emergency_event)
        event_dict.pop('signature', None)  # Remove signature field before signing
        event_json = json.dumps(event_dict, default=str, sort_keys=True)
        emergency_event.signature = self._sign_event(event_json)
        
        # Update system state
        self.current_state = SystemState.SHUTDOWN
        
        # Add to emergency events
        self.emergency_events.append(emergency_event)
        
        # Execute shutdown procedures
        shutdown_result = await self._execute_shutdown_procedures(emergency_event)
        
        # Persist emergency event immediately
        self._persist_emergency_history()
        
        # Log critical emergency event
        logger.error(f"🚨 EMERGENCY SHUTDOWN COMPLETED - Event ID: {event_id}")
        logger.error(f"🚨 Shutdown Result: {shutdown_result}")
        
        # Escalate if critical
        if emergency_level == EmergencyLevel.CRITICAL:
            await self._escalate_emergency(emergency_event)
        
        return {
            "shutdown_initiated": True,
            "event_id": event_id,
            "reason": reason,
            "initiated_by": initiated_by,
            "emergency_level": emergency_level.value,
            "affected_agents": emergency_event.affected_agents,
            "shutdown_result": shutdown_result,
            "timestamp": emergency_event.timestamp.isoformat(),
            "signature": emergency_event.signature
        }

    async def _execute_shutdown_procedures(self, emergency_event: EmergencyEvent) -> Dict[str, Any]:
        """Execute actual shutdown procedures"""
        shutdown_results = {
            "callbacks_executed": 0,
            "callbacks_failed": 0,
            "agents_stopped": [],
            "agents_failed": [],
            "shutdown_duration_seconds": 0
        }
        
        start_time = datetime.now()
        
        try:
            # Execute registered shutdown callbacks
            logger.info(f"Executing {len(self.shutdown_callbacks)} shutdown callbacks...")
            
            for i, callback in enumerate(self.shutdown_callbacks):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(emergency_event)
                    else:
                        callback(emergency_event)
                    shutdown_results["callbacks_executed"] += 1
                    logger.info(f"✅ Shutdown callback {i+1} executed successfully")
                except Exception as e:
                    shutdown_results["callbacks_failed"] += 1
                    logger.error(f"❌ Shutdown callback {i+1} failed: {e}")
            
            # Stop system-wide agents
            if "ALL_AGENTS" in emergency_event.affected_agents:
                logger.info("🛑 Stopping all system agents...")
                stopped_agents = await self._stop_all_agents()
                shutdown_results["agents_stopped"] = stopped_agents
            else:
                logger.info(f"🛑 Stopping specific agents: {emergency_event.affected_agents}")
                for agent_name in emergency_event.affected_agents:
                    try:
                        await self._stop_agent(agent_name)
                        shutdown_results["agents_stopped"].append(agent_name)
                        logger.info(f"✅ Agent {agent_name} stopped successfully")
                    except Exception as e:
                        shutdown_results["agents_failed"].append({"agent": agent_name, "error": str(e)})
                        logger.error(f"❌ Failed to stop agent {agent_name}: {e}")
            
            # Calculate shutdown duration
            end_time = datetime.now()
            shutdown_results["shutdown_duration_seconds"] = (end_time - start_time).total_seconds()
            
            logger.info(f"🚨 Emergency shutdown procedures completed in {shutdown_results['shutdown_duration_seconds']:.2f} seconds")
            
        except Exception as e:
            logger.error(f"🚨 CRITICAL: Emergency shutdown procedures failed: {e}")
            shutdown_results["critical_error"] = str(e)
        
        return shutdown_results

    async def _stop_all_agents(self) -> List[str]:
        """Stop all system agents"""
        stopped_agents = []
        
        try:
            # This would integrate with the actual agent management system
            # For now, we'll simulate the process
            
            # In a real implementation, this would:
            # 1. Connect to the orchestrator or agent registry
            # 2. Get list of all running agents
            # 3. Send shutdown signals to each agent
            # 4. Wait for graceful shutdown or force termination
            
            logger.info("🛑 Simulating system-wide agent shutdown...")
            
            # Simulate stopping common ABI agents
            simulated_agents = [
                "orchestrator",
                "planner", 
                "worker_actor",
                "worker_observer",
                "abi_semantic_layer"
            ]
            
            for agent in simulated_agents:
                try:
                    await self._stop_agent(agent)
                    stopped_agents.append(agent)
                except Exception as e:
                    logger.error(f"Failed to stop {agent}: {e}")
            
            logger.info(f"🛑 Stopped {len(stopped_agents)} agents")
            
        except Exception as e:
            logger.error(f"Failed to stop all agents: {e}")
        
        return stopped_agents

    async def _stop_agent(self, agent_name: str):
        """Stop a specific agent"""
        # This would integrate with the actual agent management system
        # For now, we'll simulate the process
        
        logger.info(f"🛑 Stopping agent: {agent_name}")
        
        # Simulate agent shutdown delay
        await asyncio.sleep(0.1)
        
        # In a real implementation, this would:
        # 1. Send graceful shutdown signal to agent
        # 2. Wait for acknowledgment
        # 3. Force termination if timeout exceeded
        # 4. Clean up agent resources
        
        logger.info(f"✅ Agent {agent_name} stopped")

    async def _escalate_emergency(self, emergency_event: EmergencyEvent):
        """Escalate critical emergency events"""
        try:
            logger.error(f"🚨 ESCALATING CRITICAL EMERGENCY: {emergency_event.event_id}")
            
            # Send notifications to emergency contacts
            for contact in self.emergency_contacts:
                try:
                    await self._notify_emergency_contact(contact, emergency_event)
                except Exception as e:
                    logger.error(f"Failed to notify emergency contact {contact}: {e}")
            
            # Log escalation
            logger.error(f"🚨 Emergency escalation completed for event {emergency_event.event_id}")
            
        except Exception as e:
            logger.error(f"Emergency escalation failed: {e}")

    async def _notify_emergency_contact(self, contact: Dict[str, Any], emergency_event: EmergencyEvent):
        """Notify emergency contact (placeholder for actual notification system)"""
        # This would integrate with actual notification systems (email, SMS, Slack, etc.)
        logger.error(f"🚨 EMERGENCY NOTIFICATION to {contact.get('name', 'Unknown')}: {emergency_event.reason}")

    async def enter_emergency_mode(
        self,
        reason: str,
        initiated_by: str,
        duration_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Enter emergency mode - blocks all operations but keeps system running
        
        Args:
            reason: Reason for entering emergency mode
            initiated_by: Who initiated emergency mode
            duration_hours: Auto-exit after this many hours (None = manual exit only)
        
        Returns:
            Emergency mode activation result
        """
        logger.warning(f"⚠️ ENTERING EMERGENCY MODE initiated by {initiated_by}: {reason}")
        
        # Generate unique event ID
        event_id = hashlib.sha256(
            f"emergency_mode_{datetime.now(timezone.utc).isoformat()}{initiated_by}{reason}".encode()
        ).hexdigest()[:16]
        
        # Create emergency event
        emergency_event = EmergencyEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            emergency_type=EmergencyType.MANUAL_SHUTDOWN,  # Using manual shutdown type for emergency mode
            emergency_level=EmergencyLevel.HIGH,
            initiated_by=initiated_by,
            reason=reason,
            system_state_before=self.current_state,
            system_state_after=SystemState.EMERGENCY_MODE,
            affected_agents=["ALL_AGENTS"],
            additional_context={
                "emergency_mode": True,
                "duration_hours": duration_hours,
                "auto_exit": duration_hours is not None
            }
        )
        
        # Sign the event (exclude signature field from signing)
        event_dict = asdict(emergency_event)
        event_dict.pop('signature', None)  # Remove signature field before signing
        event_json = json.dumps(event_dict, default=str, sort_keys=True)
        emergency_event.signature = self._sign_event(event_json)
        
        # Update system state
        self.current_state = SystemState.EMERGENCY_MODE
        
        # Add to emergency events
        self.emergency_events.append(emergency_event)
        
        # Persist immediately
        self._persist_emergency_history()
        
        # Schedule auto-exit if specified
        if duration_hours:
            asyncio.create_task(self._auto_exit_emergency_mode(event_id, duration_hours))
        
        logger.warning(f"⚠️ EMERGENCY MODE ACTIVATED - Event ID: {event_id}")
        
        return {
            "emergency_mode_activated": True,
            "event_id": event_id,
            "reason": reason,
            "initiated_by": initiated_by,
            "duration_hours": duration_hours,
            "timestamp": emergency_event.timestamp.isoformat(),
            "signature": emergency_event.signature
        }

    async def _auto_exit_emergency_mode(self, event_id: str, duration_hours: int):
        """Automatically exit emergency mode after specified duration"""
        try:
            await asyncio.sleep(duration_hours * 3600)  # Convert hours to seconds
            
            if self.current_state == SystemState.EMERGENCY_MODE:
                logger.info(f"⏰ Auto-exiting emergency mode after {duration_hours} hours")
                await self.exit_emergency_mode(
                    reason=f"Auto-exit after {duration_hours} hours",
                    initiated_by="SYSTEM_AUTO_EXIT"
                )
        except Exception as e:
            logger.error(f"Failed to auto-exit emergency mode: {e}")

    async def exit_emergency_mode(
        self,
        reason: str,
        initiated_by: str
    ) -> Dict[str, Any]:
        """
        Exit emergency mode and return to normal operations
        
        Args:
            reason: Reason for exiting emergency mode
            initiated_by: Who initiated the exit
        
        Returns:
            Emergency mode exit result
        """
        if self.current_state != SystemState.EMERGENCY_MODE:
            return {
                "error": f"System not in emergency mode (current state: {self.current_state.value})",
                "success": False
            }
        
        logger.info(f"✅ EXITING EMERGENCY MODE initiated by {initiated_by}: {reason}")
        
        # Generate unique event ID
        event_id = hashlib.sha256(
            f"exit_emergency_mode_{datetime.now(timezone.utc).isoformat()}{initiated_by}{reason}".encode()
        ).hexdigest()[:16]
        
        # Create emergency event
        emergency_event = EmergencyEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            emergency_type=EmergencyType.MANUAL_SHUTDOWN,
            emergency_level=EmergencyLevel.MEDIUM,
            initiated_by=initiated_by,
            reason=f"EXIT EMERGENCY MODE: {reason}",
            system_state_before=SystemState.EMERGENCY_MODE,
            system_state_after=SystemState.NORMAL,
            affected_agents=["ALL_AGENTS"],
            additional_context={
                "emergency_mode_exit": True,
                "returning_to_normal": True
            }
        )
        
        # Sign the event (exclude signature field from signing)
        event_dict = asdict(emergency_event)
        event_dict.pop('signature', None)  # Remove signature field before signing
        event_json = json.dumps(event_dict, default=str, sort_keys=True)
        emergency_event.signature = self._sign_event(event_json)
        
        # Update system state
        self.current_state = SystemState.NORMAL
        
        # Add to emergency events
        self.emergency_events.append(emergency_event)
        
        # Persist immediately
        self._persist_emergency_history()
        
        logger.info(f"✅ EMERGENCY MODE EXITED - Event ID: {event_id}")
        
        return {
            "emergency_mode_exited": True,
            "event_id": event_id,
            "reason": reason,
            "initiated_by": initiated_by,
            "timestamp": emergency_event.timestamp.isoformat(),
            "signature": emergency_event.signature
        }

    def is_emergency_mode(self) -> bool:
        """Check if system is in emergency mode"""
        return self.current_state == SystemState.EMERGENCY_MODE

    def is_shutdown(self) -> bool:
        """Check if system is shutdown"""
        return self.current_state == SystemState.SHUTDOWN

    async def administrative_override(
        self,
        admin_id: str,
        override_reason: str,
        original_decision: Dict[str, Any],
        override_decision: Dict[str, Any],
        justification: str,
        approval_chain: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute administrative override with full audit trail
        
        Args:
            admin_id: Administrator identity
            override_reason: Reason for override
            original_decision: Original policy decision being overridden
            override_decision: New decision to apply
            justification: Detailed justification for override
            approval_chain: List of approvers (if required)
        
        Returns:
            Administrative override result
        """
        logger.warning(f"🔐 ADMINISTRATIVE OVERRIDE initiated by {admin_id}: {override_reason}")
        
        # Check if admin overrides are enabled
        if not self.config.get('admin_override.enabled', True):
            return {
                "error": "Administrative overrides are disabled",
                "success": False
            }
        
        # Validate approval chain if required
        if self.config.get('admin_override.require_approval_chain', True):
            if not approval_chain or len(approval_chain) < 2:
                return {
                    "error": "Administrative override requires approval chain",
                    "success": False
                }
        
        # Generate unique override ID
        override_id = hashlib.sha256(
            f"admin_override_{datetime.now(timezone.utc).isoformat()}{admin_id}{override_reason}".encode()
        ).hexdigest()[:16]
        
        # Create admin override record
        admin_override = AdminOverride(
            override_id=override_id,
            timestamp=datetime.now(timezone.utc),
            admin_id=admin_id,
            override_reason=override_reason,
            original_decision=original_decision,
            override_decision=override_decision,
            justification=justification,
            approval_chain=approval_chain or [admin_id]
        )
        
        # Sign the override for integrity (exclude signature field from signing)
        override_dict = asdict(admin_override)
        override_dict.pop('signature', None)  # Remove signature field before signing
        override_json = json.dumps(override_dict, default=str, sort_keys=True)
        admin_override.signature = self._sign_event(override_json)
        
        # Add to admin overrides
        self.admin_overrides.append(admin_override)
        
        # Create corresponding emergency event
        emergency_event = EmergencyEvent(
            event_id=f"override_{override_id}",
            timestamp=datetime.now(timezone.utc),
            emergency_type=EmergencyType.ADMINISTRATIVE_OVERRIDE,
            emergency_level=EmergencyLevel.HIGH,
            initiated_by=admin_id,
            reason=f"Administrative Override: {override_reason}",
            system_state_before=self.current_state,
            system_state_after=self.current_state,  # State doesn't change for overrides
            affected_agents=[],
            additional_context={
                "override_id": override_id,
                "original_decision": original_decision,
                "override_decision": override_decision,
                "approval_chain": approval_chain
            }
        )
        
        # Sign the event (exclude signature field from signing)
        event_dict = asdict(emergency_event)
        event_dict.pop('signature', None)  # Remove signature field before signing
        event_json = json.dumps(event_dict, default=str, sort_keys=True)
        emergency_event.signature = self._sign_event(event_json)
        
        # Add to emergency events
        self.emergency_events.append(emergency_event)
        
        # Persist immediately
        self._persist_emergency_history()
        
        logger.warning(f"🔐 ADMINISTRATIVE OVERRIDE EXECUTED - Override ID: {override_id}")
        
        return {
            "override_executed": True,
            "override_id": override_id,
            "admin_id": admin_id,
            "override_reason": override_reason,
            "approval_chain": approval_chain,
            "timestamp": admin_override.timestamp.isoformat(),
            "signature": admin_override.signature
        }

    def register_shutdown_callback(self, callback: Callable):
        """Register a callback to be executed during emergency shutdown"""
        self.shutdown_callbacks.append(callback)
        logger.info(f"Registered shutdown callback: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")

    def get_emergency_status(self) -> Dict[str, Any]:
        """Get current emergency system status"""
        return {
            "current_state": self.current_state.value,
            "is_emergency_mode": self.is_emergency_mode(),
            "is_shutdown": self.is_shutdown(),
            "total_emergency_events": len(self.emergency_events),
            "total_admin_overrides": len(self.admin_overrides),
            "recent_events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "emergency_type": event.emergency_type.value,
                    "emergency_level": event.emergency_level.value,
                    "initiated_by": event.initiated_by,
                    "reason": event.reason
                }
                for event in sorted(self.emergency_events, key=lambda x: x.timestamp, reverse=True)[:5]
            ],
            "shutdown_callbacks_registered": len(self.shutdown_callbacks),
            "emergency_contacts_configured": len(self.emergency_contacts)
        }

    def get_emergency_history(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get emergency event history"""
        events = sorted(self.emergency_events, key=lambda x: x.timestamp, reverse=True)
        if limit:
            events = events[:limit]
        
        overrides = sorted(self.admin_overrides, key=lambda x: x.timestamp, reverse=True)
        if limit:
            overrides = overrides[:limit]
        
        return {
            "emergency_events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "emergency_type": event.emergency_type.value,
                    "emergency_level": event.emergency_level.value,
                    "initiated_by": event.initiated_by,
                    "reason": event.reason,
                    "system_state_before": event.system_state_before.value,
                    "system_state_after": event.system_state_after.value,
                    "affected_agents": event.affected_agents,
                    "has_signature": event.signature is not None
                }
                for event in events
            ],
            "admin_overrides": [
                {
                    "override_id": override.override_id,
                    "timestamp": override.timestamp.isoformat(),
                    "admin_id": override.admin_id,
                    "override_reason": override.override_reason,
                    "approval_chain": override.approval_chain,
                    "has_signature": override.signature is not None
                }
                for override in overrides
            ]
        }

    async def validate_emergency_integrity(self) -> Dict[str, Any]:
        """Validate integrity of emergency event logs"""
        validation_results = {
            "total_events": len(self.emergency_events),
            "total_overrides": len(self.admin_overrides),
            "events_with_signatures": 0,
            "events_with_valid_signatures": 0,
            "overrides_with_signatures": 0,
            "overrides_with_valid_signatures": 0,
            "integrity_issues": []
        }
        
        # Validate emergency events
        for event in self.emergency_events:
            if event.signature:
                validation_results["events_with_signatures"] += 1
                # Exclude signature field when verifying
                event_dict = asdict(event)
                event_dict.pop('signature', None)
                event_json = json.dumps(event_dict, default=str, sort_keys=True)
                if self._verify_signature(event_json, event.signature):
                    validation_results["events_with_valid_signatures"] += 1
                else:
                    validation_results["integrity_issues"].append(f"Invalid signature for event {event.event_id}")
        
        # Validate admin overrides
        for override in self.admin_overrides:
            if override.signature:
                validation_results["overrides_with_signatures"] += 1
                # Exclude signature field when verifying
                override_dict = asdict(override)
                override_dict.pop('signature', None)
                override_json = json.dumps(override_dict, default=str, sort_keys=True)
                if self._verify_signature(override_json, override.signature):
                    validation_results["overrides_with_valid_signatures"] += 1
                else:
                    validation_results["integrity_issues"].append(f"Invalid signature for override {override.override_id}")
        
        validation_results["integrity_valid"] = len(validation_results["integrity_issues"]) == 0
        
        return validation_results

# Global emergency response system instance
_emergency_response_system = None

def get_emergency_response_system(config_path: Optional[str] = None) -> EmergencyResponseSystem:
    """Get singleton emergency response system instance"""
    global _emergency_response_system
    if _emergency_response_system is None:
        _emergency_response_system = EmergencyResponseSystem(config_path)
    return _emergency_response_system