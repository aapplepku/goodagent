"""Simulator implementations of provider contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, field_validator, model_validator

from open_commerce.core.enums import EventType, ExecutionStatus, ProviderType
from open_commerce.core.events import BehavioralEvent
from open_commerce.core.money import Money
from open_commerce.core.providers import (
    CampaignSnapshot,
    CapabilitySet,
    CreateDiscountCommand,
    DisableDiscountCommand,
    ExecutionRef,
    ProviderResult,
    ReconciliationResult,
    SetCampaignBudgetCommand,
    SetRecommendationPolicyCommand,
    SetVariantPricesCommand,
    StoreSnapshot,
    SyncPage,
)
from open_commerce.core.types import JsonObject, SafeError, StrictDomainModel, ensure_utc
from open_commerce.simulator.engine import summarize_catalog
from open_commerce.simulator.merchandising_models import RecommendationPolicyState
from open_commerce.simulator.models import (
    DiscountState,
    SearchBoostState,
    SimulatorCommandRecord,
    SimulatorState,
)
from open_commerce.simulator.scenarios import SIMULATOR_CAPABILITIES
from open_commerce.simulator.targets import observed_command_state


class SetSearchBoostCommand(StrictDomainModel):
    """Simulator command to set internal search exposure state."""

    tenant_id: UUID
    idempotency_key: str
    query_text: str
    multiplier: Decimal = Field(gt=0, le=Decimal("3"))
    starts_at: datetime
    ends_at: datetime
    category: str | None = None
    product_ids: list[str] = Field(default_factory=list)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_window(self) -> SetSearchBoostCommand:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class SimulatorProvider:
    """Provider-compatible facade over one simulator instance."""

    def __init__(self, state: SimulatorState) -> None:
        self.state = state

    async def capabilities(self) -> CapabilitySet:
        """Return simulator provider capabilities."""

        return CapabilitySet(
            provider_type=ProviderType.SIMULATOR,
            capabilities=SIMULATOR_CAPABILITIES,
            limits={
                "no_inventory_writes": True,
                "max_search_boost_multiplier": "3.0",
                "max_price_change_rate": "0.50",
            },
        )

    async def sync_catalog(self, cursor: str | None) -> SyncPage:
        """Return deterministic catalog pages."""

        page_size = 100
        offset = int(cursor or "0")
        items = [
            cast(JsonObject, product.model_dump(mode="json"))
            for product in self.state.products[offset : offset + page_size]
        ]
        next_offset = offset + page_size
        return SyncPage(
            items=items,
            next_cursor=str(next_offset) if next_offset < len(self.state.products) else None,
        )

    async def get_store_snapshot(self, as_of: datetime) -> StoreSnapshot:
        """Return a redacted aggregate simulator store snapshot."""

        catalog = summarize_catalog(self.state.products)
        latest = self.state.metrics[-1] if self.state.metrics else None
        return StoreSnapshot(
            tenant_id=self.state.tenant_id,
            as_of=as_of,
            catalog_summary=cast(JsonObject, catalog.model_dump(mode="json")),
            inventory_summary={
                "total_units": catalog.inventory_units,
                "low_stock_products": catalog.low_stock_products,
                "excess_inventory_products": catalog.excess_inventory_products,
            },
            order_summary=cast(JsonObject, latest.model_dump(mode="json") if latest else {}),
            discount_summary={
                "active_discounts": sum(1 for discount in self.state.discounts if discount.active)
            },
        )

    async def get_campaigns(self, as_of: datetime) -> list[CampaignSnapshot]:
        """Return campaign snapshots."""

        observed_at = ensure_utc(as_of)
        return [
            CampaignSnapshot(
                tenant_id=self.state.tenant_id,
                campaign_id=campaign.id,
                name=campaign.name,
                channel_id=campaign.channel_id,
                daily_budget=Money(
                    amount_minor=campaign.daily_budget_minor,
                    currency="USD",
                ),
                active=campaign.active,
                observed_at=observed_at,
                metrics={"max_reach": campaign.max_reach},
            )
            for campaign in self.state.campaigns
        ]

    async def create_discount(self, command: CreateDiscountCommand) -> ProviderResult:
        """Create an idempotent simulator discount."""

        if command.tenant_id != self.state.tenant_id:
            return _failed("TENANT_MISMATCH", "command tenant does not match simulator instance")
        existing = _record_for(self.state, "create_discount", command.idempotency_key)
        if existing is not None:
            return _result_from_record(existing)

        before: JsonObject = {
            "discounts": [discount.model_dump(mode="json") for discount in self.state.discounts]
        }
        discount_id = _stable_resource_id(self.state.id, "discount", command.idempotency_key)
        discount = DiscountState(
            id=discount_id,
            code=command.code,
            discount_kind=command.discount_kind,
            value=Decimal(command.value),
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            product_ids=_string_list(command.product_scope.get("product_ids")),
            category_paths=_string_list(command.product_scope.get("category_paths")),
            created_by_command=command.idempotency_key,
            maximum_cost_minor=command.maximum_cost_minor,
            minimum_subtotal_minor=command.minimum_subtotal_minor,
            new_customers_only=command.new_customers_only,
        )
        self.state.discounts.append(discount)
        after: JsonObject = {
            "discount": discount.model_dump(
                mode="json", exclude={"spent_minor", "spend_cap_for_day_minor"}
            )
        }
        record = _append_record(
            state=self.state,
            action_type="create_discount",
            idempotency_key=command.idempotency_key,
            before_state=before,
            after_state=after,
        )
        return _result_from_record(record, provider_resource_id=discount.id)

    async def disable_discount(self, command: DisableDiscountCommand) -> ProviderResult:
        """Disable an idempotent simulator discount."""

        if command.tenant_id != self.state.tenant_id:
            return _failed("TENANT_MISMATCH", "command tenant does not match simulator instance")
        existing = _record_for(self.state, "disable_discount", command.idempotency_key)
        if existing is not None:
            return _result_from_record(existing)

        discount = _find_discount(self.state, command.provider_discount_id)
        if discount is None:
            return _failed("DISCOUNT_NOT_FOUND", "discount does not exist")
        before: JsonObject = {
            "discount": discount.model_dump(
                mode="json", exclude={"spent_minor", "spend_cap_for_day_minor"}
            )
        }
        discount.active = False
        after: JsonObject = {
            "discount": discount.model_dump(
                mode="json", exclude={"spent_minor", "spend_cap_for_day_minor"}
            )
        }
        record = _append_record(
            state=self.state,
            action_type="disable_discount",
            idempotency_key=command.idempotency_key,
            before_state=before,
            after_state=after,
        )
        return _result_from_record(record, provider_resource_id=discount.id)

    async def set_variant_prices(self, command: SetVariantPricesCommand) -> ProviderResult:
        """Set simulator variant prices with basic bounded validity checks."""

        if command.tenant_id != self.state.tenant_id:
            return _failed("TENANT_MISMATCH", "command tenant does not match simulator instance")
        existing = _record_for(self.state, "set_variant_price", command.idempotency_key)
        if existing is not None:
            return _result_from_record(existing)

        merch = self.state.merchandising
        if merch is not None:
            window = command.window
            if (
                window is None
                or window.start_at != self.state.current_time
                or not 24 * 3600
                <= (window.end_at - window.start_at).total_seconds()
                <= merch.constraints.max_duration_hours * 3600
            ):
                return _failed("INVALID_PRICE_WINDOW", "review a bounded current price window")

        variant_by_id = {
            variant.id: variant for product in self.state.products for variant in product.variants
        }
        before_changes: list[JsonObject] = []
        after_changes: list[JsonObject] = []
        seen_ids: set[str] = set()
        for change in command.changes:
            variant_id = str(change.get("variant_id", ""))
            if variant_id in seen_ids:
                return _failed("DUPLICATE_VARIANT", "one price change per variant is required")
            seen_ids.add(variant_id)
            new_price = change.get("new_price_minor")
            if not isinstance(new_price, int) or isinstance(new_price, bool):
                return _failed("INVALID_PRICE", "new_price_minor must be an integer")
            variant = variant_by_id.get(variant_id)
            if variant is None:
                return _failed("VARIANT_NOT_FOUND", "variant does not exist")
            if merch is not None:
                from open_commerce.simulator.merchandising_economics import candidate_economics

                if (command.current_versions or {}).get(variant_id) != merch.prices[
                    variant_id
                ].version:
                    return _failed("STALE_PRICE_VERSION", "price revision changed")
                candidate = candidate_economics(
                    self.state,
                    tenant_id=command.tenant_id,
                    product_id=str(change.get("product_id", "")),
                    variant_id=variant_id,
                    base_price_minor=new_price,
                    promotion_rate=Decimal(0),
                )
                if not candidate.eligible:
                    return _failed("PRICE_ECONOMICS_BOUNDS", "current combined price bounds failed")
            lower = int(Decimal(variant.price_minor) * Decimal("0.50"))
            upper = int(Decimal(variant.price_minor) * Decimal("1.50"))
            if not lower <= new_price <= upper:
                return _failed("PRICE_OUT_OF_BOUNDS", "price change exceeds simulator bounds")
            before_changes.append({"variant_id": variant.id, "price_minor": variant.price_minor})
            after_changes.append({"variant_id": variant.id, "price_minor": new_price})

        # Validate the complete command before mutating any variant.
        for item in after_changes:
            if merch is not None:
                variant_id = str(item["variant_id"])
                revision = merch.prices[variant_id]
                current_price = variant_by_id[variant_id].price_minor
                revision.cumulative_change_minor += abs(
                    int(str(item["price_minor"])) - current_price
                )
                revision.version += 1
                revision.last_changed_at = self.state.current_time
                revision.revert_price_minor = current_price
                assert command.window is not None
                revision.expires_at = command.window.end_at
                revision.command_key = command.idempotency_key
                item["price_revision"] = revision.model_dump(mode="json")
            variant_by_id[str(item["variant_id"])].price_minor = int(str(item["price_minor"]))

        record = _append_record(
            state=self.state,
            action_type="set_variant_price",
            idempotency_key=command.idempotency_key,
            before_state={"changes": before_changes},
            after_state={"changes": after_changes},
        )
        return _result_from_record(record)

    async def set_campaign_budget(self, command: SetCampaignBudgetCommand) -> ProviderResult:
        """Set a simulator campaign daily budget."""

        if self.state.merchandising is not None:
            return _failed("ADS_PROHIBITED", "merchandising cannot buy traffic")

        if command.tenant_id != self.state.tenant_id:
            return _failed("TENANT_MISMATCH", "command tenant does not match simulator instance")
        existing = _record_for(self.state, "set_campaign_budget", command.idempotency_key)
        if existing is not None:
            return _result_from_record(existing)

        campaign = next(
            (item for item in self.state.campaigns if item.id == command.campaign_id),
            None,
        )
        if campaign is None:
            return _failed("CAMPAIGN_NOT_FOUND", "campaign does not exist")
        before = {
            "campaign_id": campaign.id,
            "daily_budget_minor": campaign.daily_budget_minor,
        }
        campaign.daily_budget_minor = command.budget.amount_minor
        after = {
            "campaign_id": campaign.id,
            "daily_budget_minor": campaign.daily_budget_minor,
        }
        record = _append_record(
            state=self.state,
            action_type="set_campaign_budget",
            idempotency_key=command.idempotency_key,
            before_state=before,
            after_state=after,
        )
        return _result_from_record(record, provider_resource_id=campaign.id)

    async def set_search_boost(self, command: SetSearchBoostCommand) -> ProviderResult:
        """Set an internal search exposure boost."""

        if command.tenant_id != self.state.tenant_id:
            return _failed("TENANT_MISMATCH", "command tenant does not match simulator instance")
        existing = _record_for(self.state, "set_search_boost", command.idempotency_key)
        if existing is not None:
            return _result_from_record(existing)

        before: JsonObject = {
            "search_boosts": [boost.model_dump(mode="json") for boost in self.state.search_boosts]
        }
        boost = SearchBoostState(
            id=_stable_resource_id(self.state.id, "search_boost", command.idempotency_key),
            query_text=command.query_text,
            category=command.category,
            product_ids=command.product_ids,
            multiplier=command.multiplier,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            created_by_command=command.idempotency_key,
        )
        self.state.search_boosts.append(boost)
        record = _append_record(
            state=self.state,
            action_type="set_search_boost",
            idempotency_key=command.idempotency_key,
            before_state=before,
            after_state={"search_boost": boost.model_dump(mode="json")},
        )
        return _result_from_record(record, provider_resource_id=boost.id)

    async def no_op(self, *, tenant_id: UUID, idempotency_key: str) -> ProviderResult:
        """Record an idempotent no-op provider command."""

        if tenant_id != self.state.tenant_id:
            return _failed("TENANT_MISMATCH", "command tenant does not match simulator instance")
        existing = _record_for(self.state, "no_op", idempotency_key)
        if existing is not None:
            return _result_from_record(existing)
        record = _append_record(
            state=self.state,
            action_type="no_op",
            idempotency_key=idempotency_key,
            before_state={},
            after_state={},
        )
        return _result_from_record(record)

    async def set_recommendation_policy(
        self, command: SetRecommendationPolicyCommand
    ) -> ProviderResult:
        if command.tenant_id != self.state.tenant_id:
            return _failed("TENANT_MISMATCH", "command tenant mismatch")
        existing = _record_for(self.state, "set_recommendation_policy", command.idempotency_key)
        if existing is not None:
            return _result_from_record(existing)
        merch = self.state.merchandising
        if merch is None:
            return _failed("PROFILE_REQUIRED", "merchandising profile required")
        if command.expected_version != merch.recommendation_policy.version:
            return _failed("STALE_RECOMMENDATION_POLICY_VERSION", "policy revision changed")
        duration = (command.window.end_at - command.window.start_at).total_seconds()
        if (
            command.window.start_at != self.state.current_time
            or not 24 * 3600 <= duration <= merch.constraints.max_duration_hours * 3600
        ):
            return _failed("INVALID_POLICY_WINDOW", "review a bounded current policy window")
        if command.controls.minimum_relevance < merch.constraints.minimum_relevance or set(
            command.controls.excluded_product_ids
        ) - {p.id for p in self.state.products}:
            return _failed("INVALID_POLICY_CONTROLS", "policy controls violate catalog constraints")
        if command.controls.strategy == "complements" and not merch.compatibility:
            return _failed("COMPATIBILITY_REQUIRED", "no explicit catalog compatibility evidence")
        before: JsonObject = {
            "recommendation_policy": merch.recommendation_policy.model_dump(mode="json")
        }
        merch.recommendation_policy = RecommendationPolicyState(
            version=command.expected_version + 1,
            controls=command.controls.model_copy(deep=True),
            starts_at=command.window.start_at,
            ends_at=command.window.end_at,
            command_key=command.idempotency_key,
        )
        record = _append_record(
            state=self.state,
            action_type="set_recommendation_policy",
            idempotency_key=command.idempotency_key,
            before_state=before,
            after_state={
                "recommendation_policy": merch.recommendation_policy.model_dump(mode="json")
            },
        )
        return _result_from_record(record)

    async def rollback(self, *, execution_id: UUID, idempotency_key: str) -> ProviderResult:
        """Rollback a previous simulator command when state is still available."""

        source = next(
            (
                record
                for record in self.state.command_history
                if record.execution_id == execution_id
            ),
            None,
        )
        if source is None:
            return _failed("EXECUTION_NOT_FOUND", "execution does not exist")
        existing = next(
            (
                item
                for item in self.state.command_history
                if item.rollback_of == source.execution_id
            ),
            None,
        )
        if existing is not None:
            return _result_from_record(existing)

        before = observed_command_state(self.state, source)
        if before != (source.after_state or {}):
            return _failed("TARGET_CHANGED", "rollback target changed after execution")
        self._apply_rollback(source)
        after = observed_command_state(self.state, source)
        record = _append_record(
            state=self.state,
            action_type="rollback",
            idempotency_key=idempotency_key,
            before_state=before,
            after_state=after,
            rollback_of=source.execution_id,
        )
        return _result_from_record(record)

    async def reconcile(self, execution: ExecutionRef) -> ReconciliationResult:
        """Reconcile a simulator execution by reading local simulator state."""

        if execution.tenant_id != self.state.tenant_id:
            return ReconciliationResult(
                execution_id=execution.execution_id,
                status=ExecutionStatus.FAILED,
                observed_remote_state={},
                details={"code": "TENANT_MISMATCH"},
            )
        record = next(
            (
                item
                for item in self.state.command_history
                if item.execution_id == execution.execution_id
            ),
            None,
        )
        if record is None:
            return ReconciliationResult(
                execution_id=execution.execution_id,
                status=ExecutionStatus.FAILED,
                observed_remote_state={},
                details={"code": "EXECUTION_NOT_FOUND"},
            )
        observed = observed_command_state(self.state, record)
        matches = observed == (record.after_state or {})
        return ReconciliationResult(
            execution_id=execution.execution_id,
            status=ExecutionStatus.RECONCILED if matches else ExecutionStatus.UNCERTAIN,
            observed_remote_state=observed,
            details={"action_type": record.action_type, "matches_expected": matches},
        )

    async def events(self, start: datetime, end: datetime) -> AsyncIterator[BehavioralEvent]:
        """Yield normalized aggregate behavioral events for simulator history."""

        start_at = ensure_utc(start)
        end_at = ensure_utc(end)
        for event in self.state.events:
            if not start_at <= event.occurred_at < end_at:
                continue
            yield BehavioralEvent(
                event_id=event.id,
                tenant_id=self.state.tenant_id,
                occurred_at=event.occurred_at,
                session_id_hash=f"aggregate:{event.id}",
                event_type=_event_type(event.type),
                surface="simulator",
                metadata={
                    "count": event.count,
                    "dimensions": event.dimensions,
                    "metrics": event.metrics,
                },
            )

    def _apply_rollback(self, source: SimulatorCommandRecord) -> None:
        if source.action_type == "create_discount" and source.after_state is not None:
            discount_payload = source.after_state.get("discount")
            if isinstance(discount_payload, dict):
                discount = _find_discount(self.state, str(discount_payload.get("id", "")))
                if discount is not None:
                    discount.active = False
        elif source.action_type == "disable_discount":
            discount_payload = source.before_state.get("discount")
            if isinstance(discount_payload, dict):
                discount = _find_discount(self.state, str(discount_payload.get("id", "")))
                if discount is not None:
                    discount.active = bool(discount_payload.get("active", True))
        elif source.action_type == "set_variant_price":
            variant_by_id = {
                variant.id: variant
                for product in self.state.products
                for variant in product.variants
            }
            changes = source.before_state.get("changes", [])
            if isinstance(changes, list):
                for item in changes:
                    if not isinstance(item, dict):
                        continue
                    variant = variant_by_id.get(str(item.get("variant_id", "")))
                    price = item.get("price_minor")
                    if variant is not None and isinstance(price, int):
                        variant.price_minor = price
                        if self.state.merchandising is not None:
                            revision = self.state.merchandising.prices[variant.id]
                            revision.version += 1
                            revision.last_changed_at = self.state.current_time
                            revision.revert_price_minor = None
                            revision.expires_at = None
                            revision.command_key = None
        elif (
            source.action_type == "set_recommendation_policy"
            and self.state.merchandising is not None
        ):
            previous = RecommendationPolicyState.model_validate(
                source.before_state["recommendation_policy"]
            )
            previous.version = self.state.merchandising.recommendation_policy.version + 1
            self.state.merchandising.recommendation_policy = previous
        elif source.action_type == "set_campaign_budget":
            campaign_id = str(source.before_state.get("campaign_id", ""))
            budget = source.before_state.get("daily_budget_minor")
            campaign = next((item for item in self.state.campaigns if item.id == campaign_id), None)
            if campaign is not None and isinstance(budget, int):
                campaign.daily_budget_minor = budget
        elif source.action_type == "set_search_boost" and source.after_state is not None:
            boost_payload = source.after_state.get("search_boost")
            if isinstance(boost_payload, dict):
                boost_id = str(boost_payload.get("id", ""))
                for boost in self.state.search_boosts:
                    if boost.id == boost_id:
                        boost.active = False


def _failed(code: str, message: str) -> ProviderResult:
    return ProviderResult(
        status=ExecutionStatus.FAILED,
        before_state={},
        after_state=None,
        error=SafeError(code=code, message=message),
    )


def _record_for(
    state: SimulatorState,
    action_type: str,
    idempotency_key: str,
) -> SimulatorCommandRecord | None:
    return next(
        (
            record
            for record in state.command_history
            if record.action_type == action_type and record.idempotency_key == idempotency_key
        ),
        None,
    )


def _append_record(
    *,
    state: SimulatorState,
    action_type: str,
    idempotency_key: str,
    before_state: JsonObject,
    after_state: JsonObject | None,
    rollback_of: UUID | None = None,
) -> SimulatorCommandRecord:
    record = SimulatorCommandRecord(
        execution_id=uuid5(NAMESPACE_URL, f"{state.id}:{action_type}:{idempotency_key}"),
        tenant_id=state.tenant_id,
        instance_id=state.id,
        action_type=action_type,
        idempotency_key=idempotency_key,
        status=ExecutionStatus.SUCCEEDED,
        before_state=before_state,
        after_state=after_state,
        rollback_state=before_state,
        created_at=state.current_time,
        rollback_of=rollback_of,
    )
    state.command_history.append(record)
    return record


def _result_from_record(
    record: SimulatorCommandRecord,
    *,
    provider_resource_id: str | None = None,
) -> ProviderResult:
    return ProviderResult(
        status=record.status,
        provider_request_id=str(record.execution_id),
        provider_resource_id=provider_resource_id,
        before_state=record.before_state,
        after_state=record.after_state,
        reconciliation_required=False,
    )


def _find_discount(state: SimulatorState, discount_id: str) -> DiscountState | None:
    return next((discount for discount in state.discounts if discount.id == discount_id), None)


def _stable_resource_id(instance_id: UUID, kind: str, idempotency_key: str) -> str:
    return f"sim_{kind}_{uuid5(NAMESPACE_URL, f'{instance_id}:{kind}:{idempotency_key}').hex[:16]}"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _event_type(value: str) -> EventType:
    mapping = {
        "session_started": EventType.PRODUCT_VIEWED,
        "product_impression": EventType.PRODUCT_IMPRESSION,
        "product_clicked": EventType.PRODUCT_CLICKED,
        "purchase": EventType.PURCHASE,
    }
    return mapping.get(value, EventType.PRODUCT_VIEWED)
