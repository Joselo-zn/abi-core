"""Zombie Agent — Tools.

Tools are loaded dynamically from config (LIBRARY_TOOLS, TOOLS env vars)
and injected into the agent at init via ZombieAgent.__init__().
No static @agent.tool decorators needed here.
"""
