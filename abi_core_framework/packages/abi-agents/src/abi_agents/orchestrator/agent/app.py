"""Orchestrator Agent — AbiCore instance."""

from orchestrator import AbiOrchestratorAgent
from web_interface import OrchestratorWebinterface
from abi_core.agent import AbiCore

agent = AbiCore(
    web_interface_cls=OrchestratorWebinterface,
    interface_name="Orchestrator Web Interface",
)
