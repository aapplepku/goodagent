"""Conversational commerce-manager agent with bounded durable memory."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_commerce.manager_agent.agent import ManagerReActAgent
    from open_commerce.manager_agent.service import DurableManagerAgentService

__all__ = ["DurableManagerAgentService", "ManagerReActAgent"]


def __getattr__(name: str) -> object:
    # Provider contracts must be importable without loading services and their tools.
    if name == "ManagerReActAgent":
        from open_commerce.manager_agent.agent import ManagerReActAgent

        return ManagerReActAgent
    if name == "DurableManagerAgentService":
        from open_commerce.manager_agent.service import DurableManagerAgentService

        return DurableManagerAgentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
