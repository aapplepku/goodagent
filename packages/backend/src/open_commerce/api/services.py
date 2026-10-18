"""Typed production services with explicit support for isolated unit fixtures."""

from collections.abc import Awaitable

from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.service import ControllerService
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.service import SearchService
from open_commerce.simulator.durable import DurableSimulatorService
from open_commerce.simulator.service import SimulatorService

type ControllerRuntime = DurableControllerService | ControllerService
type SimulatorRuntime = DurableSimulatorService | SimulatorService
type SearchRuntime = DurableSearchService | SearchService


async def resolve[T](value: T | Awaitable[T]) -> T:
    """Await deployed database services; offline unit fixtures may be synchronous."""
    if isinstance(value, Awaitable):
        return await value
    return value
