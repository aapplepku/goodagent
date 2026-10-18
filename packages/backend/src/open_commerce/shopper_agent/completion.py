"""Receipt-backed completion, without keyword routing of shopper requests."""

from typing import Annotated, Literal

from pydantic import Field, field_validator

from open_commerce.core.tool_schema import strict_tool_schema
from open_commerce.core.types import StrictDomainModel
from open_commerce.manager_agent.model_provider import ManagerToolDefinition, ManagerToolResult


class CompleteShoppingTurn(StrictDomainModel):
    kind: Literal[
        "conversation",
        "clarification",
        "catalog",
        "price_comparison",
        "memory",
        "activity",
        "blocked",
        "refusal",
    ] = Field(
        description=(
            "catalog: answer from catalog tools, including no match or a missing variant. "
            "price_comparison: answer using the price-comparison receipt. "
            "memory/activity: report that tool's result. conversation: ordinary chat without "
            "tool work. clarification: a necessary missing detail. blocked: observed tool "
            "failure. refusal: decline unsupported or unauthorized work; never claim execution."
        )
    )
    message: str = Field(min_length=1, max_length=4000)
    product_ids: list[Annotated[str, Field(min_length=1, max_length=160)]] | None = Field(
        max_length=6,
        description=(
            "Final card IDs in selection order for catalog or price_comparison; [] is valid "
            "only for catalog. Must exactly match the last successful selection. "
            "Use null for every other kind."
        ),
    )

    @field_validator("message")
    @classmethod
    def nonblank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A completed reply must not be blank")
        return value.strip()

    @field_validator("product_ids", mode="before")
    @classmethod
    def valid_card_ids(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError("Final card IDs must be a list of nonblank strings or null")
        if len(set(value)) != len(value):
            raise ValueError("Final card IDs must not contain duplicates")
        return value


COMPLETE_SHOPPING_TURN = ManagerToolDefinition(
    name="complete_shopping_turn",
    description=(
        "Finish with the answer, not a promise. Catalog answers declare product_ids matching "
        "the final selection in order; select and declare [] if none fit. Review descriptions "
        "and reselect unsuitable cards. price_comparison requires fresh arithmetic after the "
        "last search/lookup and a nonempty subset of compared IDs. All other kinds use null. "
        "memory/activity need successful receipts. conversation is ordinary chat without tool "
        "work, never a search substitute. clarification asks for a material missing detail. "
        "blocked explains an observed tool failure. refusal declines unsupported/unauthorized "
        "work, such as cart mutations or another shopper's data; do not attempt it first. "
        "Receipts and card IDs are validated, not prose meaning. This tool makes no write."
    ),
    parameters=strict_tool_schema(CompleteShoppingTurn),
)


def completion_error(reply: CompleteShoppingTurn, receipts: list[ManagerToolResult]) -> str | None:
    if reply.kind not in {"catalog", "price_comparison"} and reply.product_ids is not None:
        return "Use product_ids=null for noncatalog completion kinds."
    receipts = [item for item in receipts if item.name != COMPLETE_SHOPPING_TURN.name]
    successful = {
        item.name
        for item in receipts
        if not item.is_error
        and not item.output.get("error")
        and (
            item.output.get("ok") is True
            or (
                item.name in {"inspect_shopping_activity", "configure_activity_monitor"}
                and item.output.get("ok") is not False
            )
        )
    }
    observed_failure = any(
        item.is_error or item.output.get("error") or item.output.get("ok") is False
        for item in receipts
    )
    if reply.kind in {"catalog", "price_comparison"}:
        if reply.product_ids is None or (
            reply.kind == "price_comparison" and not reply.product_ids
        ):
            return (
                "Declare the final product_ids in card order; catalog may use [], "
                "but price_comparison requires a nonempty list."
            )
        if not successful.intersection({"catalog_search", "lookup_catalog_products"}):
            return "Read the catalog before completing a product request."
        catalog = [
            item
            for item in receipts
            if item.name
            in {
                "catalog_search",
                "lookup_catalog_products",
                "compare_catalog_prices",
                "select_catalog_products",
            }
        ]
        if (
            not catalog
            or catalog[-1].name != "select_catalog_products"
            or (catalog[-1].is_error or catalog[-1].output.get("ok") is not True)
            or catalog[-1].output.get("error")
        ):
            return (
                "Select relevant products after the last catalog operation; select [] if none fit."
            )
        selected_ids = _product_ids(catalog[-1].output.get("selected_products"))
        if (
            selected_ids is None
            or len(set(selected_ids)) != len(selected_ids)
            or reply.product_ids != selected_ids
        ):
            return (
                "Final product_ids must exactly match the last successful selection's IDs in "
                "order. Review catalog_description and call select_catalog_products again with "
                "only the final cards, then complete with those same IDs."
            )
        if reply.kind == "price_comparison":
            # A new read or comparison supersedes older evidence, even when it failed.
            comparison = next(
                (item for item in reversed(catalog) if item.name != "select_catalog_products"),
                None,
            )
            if (
                comparison is None
                or comparison.name != "compare_catalog_prices"
                or comparison.is_error
                or comparison.output.get("ok") is not True
                or comparison.output.get("error")
            ):
                return "Use a successful compare_catalog_prices after the last search or lookup."
            compared_ids = _product_ids(comparison.output.get("items"))
            if not compared_ids or not set(selected_ids).issubset(compared_ids):
                return (
                    "Comparison and selection receipts must contain valid product IDs; "
                    "select a nonempty subset of the last compared products."
                )
    elif reply.kind == "memory" and "save_shopping_memory" not in successful:
        return "No successful memory-save receipt exists; do not claim a save."
    elif reply.kind == "activity" and not successful.intersection(
        {"inspect_shopping_activity", "configure_activity_monitor"}
    ):
        return "No successful shopping-activity receipt exists."
    elif reply.kind == "blocked" and not observed_failure:
        return "No observed tool failure exists. " + _completion_guidance(successful)
    elif reply.kind == "conversation" and receipts:
        return "This turn has tool receipts, so ordinary conversation is not its result. " + (
            _completion_guidance(successful, observed_failure=observed_failure)
        )
    return None


def _completion_guidance(successful: set[str], *, observed_failure: bool = False) -> str:
    guidance = (
        'For the observed tool failure, use kind="blocked" with product_ids=null and explain '
        "the actual failed operation without claiming success. "
        if observed_failure
        else ""
    )
    guidance += (
        'For unsupported or unauthorized work, use kind="refusal" with product_ids=null. '
        "Do not attempt a forbidden action to obtain a failure receipt. "
    )
    if successful.intersection({"catalog_search", "lookup_catalog_products"}):
        guidance += (
            'For the catalog answer, use kind="catalog" with product_ids exactly matching '
            "the latest successful select_catalog_products result, including [] when none fit. "
            "Select first if needed. A missing variant or no match is not a tool failure. "
            'Use kind="price_comparison" only for a fresh successful arithmetic comparison. '
            "Do not repeat successful reads just to change the completion kind. "
        )
    if "save_shopping_memory" in successful:
        guidance += 'For the confirmed memory save, use kind="memory" and product_ids=null. '
    if successful.intersection({"inspect_shopping_activity", "configure_activity_monitor"}):
        guidance += 'For the activity result, use kind="activity" and product_ids=null. '
    return (
        guidance + "Use clarification only for a material missing detail, not a formatting error."
    )


def _product_ids(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    product_ids: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        product_id = item.get("product_id")
        if not isinstance(product_id, str) or not product_id.strip() or len(product_id) > 160:
            return None
        product_ids.append(product_id)
    return product_ids
