"""Agent loop + (future) Layer 1/2/3 agents built on it.

Public surface:
    from src.ai.agents import run_agent, AgentResult, AgentStep
"""
from src.ai.agents.loop import AgentResult, AgentStep, run_agent

__all__ = ["run_agent", "AgentResult", "AgentStep"]
