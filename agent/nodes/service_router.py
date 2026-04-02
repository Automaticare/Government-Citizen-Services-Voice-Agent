"""
Service router node.

Passthrough node that prepares state before routing.
The actual routing happens via conditional edges in graph.py.
"""

from agent.state import AgentState


def service_router(state: AgentState) -> dict:
    """Prepare state for service routing. Routing logic is in graph edges."""
    return {}
