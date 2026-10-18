"""Allowlisted read-only tools for functional manager channels."""

from __future__ import annotations

import ast
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import Field, ValidationError

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.core.redaction import redact_model_text
from open_commerce.core.types import JsonObject, StrictDomainModel, utc_now
from open_commerce.manager_agent.models import (
    ManagerAgentCapabilities,
    ManagerRuntimeComponent,
    ManagerRuntimeStatus,
    ManagerThread,
)
from open_commerce.search.agent_tools import CatalogSearchTool, CatalogSearchToolInput

if TYPE_CHECKING:
    from open_commerce.manager_agent.workspace_tools import WorkspaceTools

CodeTopic = Literal[
    "catalog_indexing",
    "search_retrieval",
    "ranking",
    "manager_agent",
    "memory",
    "status",
    "policy",
    "api",
    "workspace_ui",
]
ManagerStatusProbe = Callable[[], Awaitable[list[ManagerRuntimeComponent]]]


class InspectCodeToolInput(StrictDomainModel):
    topic: CodeTopic


class StatusRefreshToolInput(StrictDomainModel):
    minutes: int = Field(ge=0, le=60)


@dataclass(frozen=True)
class _SourceSpec:
    path: str
    symbol: str
    language: Literal["python", "typescript"] = "python"


_CODE_TOPICS: dict[CodeTopic, tuple[str, tuple[_SourceSpec, ...]]] = {
    "catalog_indexing": (
        "CSV rows are normalized into authoritative tenant records, queued durably, and only "
        "activated after the Qdrant count matches the immutable catalog count.",
        (
            _SourceSpec(
                "packages/backend/src/open_commerce/catalog/csv_import.py",
                "normalize_catalog_csv",
            ),
            _SourceSpec(
                "packages/backend/src/open_commerce/catalog/persistence.py",
                "stage_catalog_upload",
            ),
            _SourceSpec(
                "packages/backend/src/open_commerce/worker/jobs.py",
                "process_catalog_index_job",
            ),
        ),
    ),
    "search_retrieval": (
        "Search parses intent, retrieves tenant/catalog-filtered sparse and dense candidates, "
        "rechecks constraints, and returns an evaluated result set.",
        (
            _SourceSpec(
                "packages/backend/src/open_commerce/search/durable.py",
                "DurableSearchService.search",
            ),
            _SourceSpec(
                "packages/backend/src/open_commerce/search/qdrant_index.py",
                "QdrantProductSearchIndex.search",
            ),
        ),
    ),
    "ranking": (
        "Ranking uses reciprocal-rank fusion, relevance evidence, hard constraints, and bounded "
        "secondary signals; business boosts cannot rescue irrelevant products.",
        (
            _SourceSpec("packages/backend/src/open_commerce/search/index.py", "_ranked_candidate"),
            _SourceSpec("packages/backend/src/open_commerce/search/index.py", "_rrf_order"),
        ),
    ),
    "manager_agent": (
        "The manager uses a bounded model/tool loop outside database transactions, then commits "
        "the completed turn with an optimistic branch-version check.",
        (
            _SourceSpec(
                "packages/backend/src/open_commerce/manager_agent/model_agent.py",
                "ModelBackedManagerAgent.respond",
            ),
            _SourceSpec(
                "packages/backend/src/open_commerce/manager_agent/service.py",
                "DurableManagerAgentService.send_message",
            ),
        ),
    ),
    "memory": (
        "Manager and shopper memories are durable, bounded, tenant-scoped records. Only explicit "
        "preferences become long-term memory.",
        (
            _SourceSpec(
                "packages/backend/src/open_commerce/persistence/repositories/manager_agent.py",
                "ManagerAgentRepository.list_memories",
            ),
            _SourceSpec(
                "packages/backend/src/open_commerce/manager_agent/service.py",
                "_periodic_memory",
            ),
        ),
    ),
    "status": (
        "Status is an observational snapshot compiled independently from process readiness; a "
        "down UI does not make the API health endpoint fail.",
        (
            _SourceSpec(
                "packages/backend/src/open_commerce/manager_agent/tools.py",
                "ManagerToolRuntime.status",
            ),
        ),
    ),
    "policy": (
        "Commerce writes remain behind deterministic policy, exact approvals, preconditions, "
        "idempotency, audit, and rollback metadata.",
        (
            _SourceSpec(
                "packages/backend/src/open_commerce/controller/policy.py", "PolicyEngine.decide"
            ),
            _SourceSpec(
                "packages/backend/src/open_commerce/controller/policy.py",
                "ApprovalRequirementRule",
            ),
        ),
    ),
    "api": (
        "FastAPI resolves tenant context server-side and delegates manager and search work to "
        "typed application services.",
        (
            _SourceSpec("packages/backend/src/open_commerce/api/search.py", "search_products"),
            _SourceSpec(
                "packages/backend/src/open_commerce/api/manager.py", "send_manager_message"
            ),
        ),
    ),
    "workspace_ui": (
        "The manager UI maintains independent channel drafts, unread timestamps, scroll state, "
        "reply drawers, and polled status in a fixed-height collaboration workspace.",
        (
            _SourceSpec(
                "apps/web/src/components/manager-workspace.tsx",
                "export function ManagerWorkspace",
                "typescript",
            ),
            _SourceSpec(
                "apps/web/src/components/manager-workspace.tsx",
                "function ChannelDialog",
                "typescript",
            ),
        ),
    ),
}

_SEARCH_TEST_PATTERNS = (
    re.compile(
        r"^(?:please\s+)?(?:test|run|try)\s+(?:a\s+)?search(?:\s+query)?"
        r"(?:\s+for|\s*[:=])?\s+(.+)$",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:please\s+)?search\s+for\s+(.+)$", re.IGNORECASE),
)

_STATUS_REFRESH_PATTERN = re.compile(
    r"(?:(?:status|service|health)(?:\s+page)?(?:\s+auto)?(?:\s+checks?)?.*?"
    r"(?:every|to)|(?:check|refresh|poll).*?every)\s+(\d{1,3})\s*"
    r"(?:minutes?|mins?|m)\b",
    re.IGNORECASE,
)
_STATUS_REFRESH_OFF_PATTERN = re.compile(
    r"(?:(?:disable|stop|turn\s+off).{0,36}(?:status|service|health)"
    r"|(?:turn|switch|set).{0,28}(?:status|service|health).{0,28}(?:off|disabled?))",
    re.IGNORECASE,
)


class ManagerToolRuntime:
    """Application-owned runtime for manager read tools; no commerce writes are reachable."""

    def __init__(
        self,
        *,
        catalog_search: CatalogSearchTool,
        status_probe: ManagerStatusProbe | None = None,
        workspace: WorkspaceTools | None = None,
    ) -> None:
        self.catalog_search = catalog_search
        self.status_probe = status_probe
        self.workspace = workspace

    async def test_search(
        self,
        *,
        tenant_id: UUID,
        arguments: CatalogSearchToolInput,
        catalog_index: CatalogIndexStatus,
    ) -> JsonObject:
        return await self.catalog_search.run(
            tenant_id=tenant_id,
            arguments=arguments,
            source=(
                "uploaded_catalog"
                if catalog_index.status == "ready" or catalog_index.serving_catalog_id
                else "simulator_fallback"
            ),
        )

    async def status(
        self,
        *,
        catalog_index: CatalogIndexStatus,
        capabilities: ManagerAgentCapabilities,
        tenant_id: UUID | None = None,
    ) -> ManagerRuntimeStatus:
        observed = await self.status_probe() if self.status_probe is not None else []
        by_key = {item.key: item for item in observed}

        def component(
            key: str,
            label: str,
            fallback: tuple[Literal["green", "yellow", "red", "unknown"], str],
        ) -> ManagerRuntimeComponent:
            return by_key.get(
                key,
                ManagerRuntimeComponent(
                    key=key, label=label, state=fallback[0], detail=fallback[1]
                ),
            )

        postgres = component("postgres", "PostgreSQL", ("unknown", "Probe unavailable"))
        redis = component("redis", "Redis jobs", ("unknown", "Probe unavailable"))
        worker = component("worker", "Agent worker", ("unknown", "Worker heartbeat not configured"))
        qdrant = component("qdrant", "Qdrant search", ("unknown", "Probe unavailable"))
        manager_web = component(
            "manager_web", "Manager workspace", ("unknown", "Manager app probe unavailable")
        )
        shopper_web = component(
            "shopper_web", "Shopper app", ("unknown", "Shopper app probe unavailable")
        )
        if catalog_index.status == "ready":
            catalog = ManagerRuntimeComponent(
                key="catalog_index",
                label="Catalog index",
                state="green",
                detail=f"{catalog_index.indexed_product_count} products searchable",
            )
        elif catalog_index.status in {"queued", "running"}:
            catalog = ManagerRuntimeComponent(
                key="catalog_index",
                label="Catalog index",
                state="yellow",
                detail=(
                    f"{catalog_index.status}: {catalog_index.indexed_product_count}/"
                    f"{catalog_index.product_count} products"
                ),
            )
        elif catalog_index.status == "failed":
            catalog = ManagerRuntimeComponent(
                key="catalog_index",
                label="Catalog index",
                state="red",
                detail=f"Index failed: {catalog_index.error_code or 'INDEX_FAILED'}",
            )
        else:
            catalog = ManagerRuntimeComponent(
                key="catalog_index",
                label="Catalog index",
                state="yellow",
                detail="No uploaded catalog; simulator fallback remains available",
            )

        discovery_down = postgres.state == "red" or qdrant.state == "red"
        discovery_unknown = postgres.state == "unknown" or qdrant.state == "unknown"
        discovery_state: Literal["green", "yellow", "red", "unknown"] = (
            "red"
            if discovery_down
            else "unknown"
            if discovery_unknown
            else "green"
            if catalog.state == "green" or catalog_index.serving_catalog_id is not None
            else "yellow"
        )
        search = ManagerRuntimeComponent(
            key="search",
            label="Shopper search",
            state=discovery_state,
            detail=(
                "Active catalog is available for retrieval; query quality is not verified"
                if discovery_state == "green"
                else "Search dependencies are unavailable"
                if discovery_state == "red"
                else "Search is using a limited or unverified catalog path"
            ),
        )
        recommendations = ManagerRuntimeComponent(
            key="recommendations",
            label="Recommendations",
            state=discovery_state,
            detail=(
                "Similar and popular retrieval are available"
                if discovery_state == "green"
                else "Recommendation retrieval follows search dependency state"
            ),
        )
        homepage_state = (
            "red"
            if shopper_web.state == "red"
            else "unknown"
            if shopper_web.state == "unknown"
            else discovery_state
        )
        homepage = ManagerRuntimeComponent(
            key="homepage",
            label="Shopper homepage",
            state=homepage_state,
            detail=(
                "Shopper app and discovery services are reachable"
                if homepage_state == "green"
                else "Homepage is degraded with one or more unavailable dependencies"
            ),
        )
        manager_agent = ManagerRuntimeComponent(
            key="manager_agent",
            label="Manager agent",
            state="unknown" if capabilities.model_backed else "yellow",
            detail=(
                f"{capabilities.conversation_provider} / {capabilities.conversation_model}; "
                "configured, connectivity unchecked"
                if capabilities.model_backed
                else "Deterministic fallback; hosted conversation model is not configured"
            ),
        )
        manager_agent = by_key.get("manager_agent", manager_agent)
        if self.workspace is not None:
            if tenant_id is None:
                raise ValueError("Tenant ID is required for persisted connection observations")
            connection = await self.workspace.model_connection(tenant_id)
            if connection is not None:
                manager_agent = connection
        return ManagerRuntimeStatus(
            generated_at=utc_now(),
            components=[
                ManagerRuntimeComponent(
                    key="api", label="API", state="green", detail="Status endpoint responding"
                ),
                postgres,
                redis,
                qdrant,
                catalog,
                search,
                recommendations,
                manager_web,
                shopper_web,
                worker,
                homepage,
                manager_agent,
            ],
        )

    def inspect_code(self, arguments: InspectCodeToolInput) -> JsonObject:
        summary, specs = _CODE_TOPICS[arguments.topic]
        excerpts: list[JsonObject] = []
        for spec in specs:
            source = _source_excerpt(spec)
            if source is not None:
                excerpts.append(
                    {
                        "path": spec.path,
                        "symbol": spec.symbol,
                        "language": spec.language,
                        "source": redact_model_text(source),
                    }
                )
        return {
            "ok": True,
            "topic": arguments.topic,
            "summary": summary,
            "excerpts": excerpts,
            "notice": (
                "Curated read-only source excerpts only. No environment files, credentials, "
                "arbitrary paths, command execution, or write capability are exposed."
            ),
        }


def channel_allows(thread: ManagerThread, function: Literal["search", "status"]) -> bool:
    if thread.channel_kind == function:
        return True
    if thread.channel_kind != "custom":
        return False
    brief = f"{thread.title} {thread.slug or ''} {thread.description or ''}".lower()
    tokens = (
        ("search", "retrieval", "discovery", "query")
        if function == "search"
        else ("status", "health", "operations", "monitor", "reliability")
    )
    return any(token in brief for token in tokens)


def extract_search_test(content: str) -> CatalogSearchToolInput | None:
    cleaned = " ".join(content.split())
    for pattern in _SEARCH_TEST_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            return CatalogSearchToolInput(query=match.group(1), mode="hybrid", top_k=6)
    return None


def extract_status_refresh(content: str) -> StatusRefreshToolInput | None:
    """Parse only explicit status polling commands; ordinary status questions do not mutate."""

    cleaned = " ".join(content.split())
    if _STATUS_REFRESH_OFF_PATTERN.search(cleaned):
        return StatusRefreshToolInput(minutes=0)
    match = _STATUS_REFRESH_PATTERN.search(cleaned)
    if match is None:
        return None
    try:
        return StatusRefreshToolInput(minutes=int(match.group(1)))
    except ValidationError:
        return None


def is_status_question(content: str) -> bool:
    normalized = content.lower()
    return any(token in normalized for token in ("status", "health", "green", "down", "up"))


def format_search_observation(observation: JsonObject) -> str:
    query = str(observation.get("query") or "")
    mode = str(observation.get("mode") or "hybrid")
    results = observation.get("results")
    if not isinstance(results, list) or not results:
        clarification = observation.get("clarification")
        suffix = f" {clarification}" if isinstance(clarification, str) else ""
        return f'I tested "{query}" with {mode} retrieval and found no eligible products.{suffix}'
    lines = [f'Search test for "{query}" ({mode}):']
    for index, raw in enumerate(results[:6], start=1):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("product_id") or "Product")
        currency = str(raw.get("currency") or "USD")
        minor = raw.get("price_minor")
        price = f"{currency} {int(minor) / 100:.2f}" if isinstance(minor, int) else currency
        score = str(raw.get("score") or "n/a")
        lines.append(f"{index}. {title} - {price}, score {score}")
    lines.append(
        "These are live read-only results from the current catalog; no ranking settings changed."
    )
    return "\n".join(lines)


def format_runtime_status(status: ManagerRuntimeStatus) -> str:
    counts = {
        state: sum(item.state == state for item in status.components)
        for state in ("green", "yellow", "red", "unknown")
    }
    lines = [
        f"Current status: {counts['green']} green, {counts['yellow']} degraded, "
        f"{counts['red']} down, {counts['unknown']} unknown."
    ]
    for item in status.components:
        lines.append(f"- {item.label}: {item.state} - {item.detail}")
    return "\n".join(lines)


def _source_excerpt(spec: _SourceSpec) -> str | None:
    package_root = Path(__file__).resolve().parents[1]
    repository_root = package_root.parents[3]
    target = repository_root / spec.path
    try:
        source = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if spec.language == "typescript":
        start = source.find(spec.symbol)
        return _bounded_source(source[start : start + 1800]) if start >= 0 else None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    parts = spec.symbol.split(".")
    nodes: list[ast.AST] = list(tree.body)
    selected: ast.AST | None = None
    for part in parts:
        selected = next(
            (
                node
                for node in nodes
                if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == part
            ),
            None,
        )
        if selected is None:
            return None
        nodes = list(selected.body) if isinstance(selected, ast.ClassDef) else []
    excerpt = ast.get_source_segment(source, selected) if selected is not None else None
    return _bounded_source(excerpt) if excerpt else None


def _bounded_source(source: str) -> str:
    normalized = source.strip()
    return normalized if len(normalized) <= 1800 else f"{normalized[:1790]}\n# ... bounded excerpt"
