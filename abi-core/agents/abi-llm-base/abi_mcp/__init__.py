"""
ABI MCP (Model Context Protocol) client module for ABI agents.

This module provides client functionality for communicating with MCP servers.
Renamed from 'mcp' to 'abi_mcp' to avoid conflicts with external mcp library.
"""

from .client import init_session, find_agent, find_resource

__all__ = ['init_session', 'find_agent', 'find_resource']