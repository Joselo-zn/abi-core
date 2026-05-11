#!/usr/bin/env python3
"""Builder Agent — Entry point."""

from app import agent
from builder import AbiBuilderAgent

agent.run(AbiBuilderAgent())
