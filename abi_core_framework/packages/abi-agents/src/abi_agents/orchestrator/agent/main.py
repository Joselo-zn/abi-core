#!/usr/bin/env python3
"""Orchestrator Agent — Entry point."""

from app import agent
from orchestrator import AbiOrchestratorAgent

agent.run(AbiOrchestratorAgent())
