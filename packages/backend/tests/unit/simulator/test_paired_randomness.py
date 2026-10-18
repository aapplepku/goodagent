"""Check engine draw alignment under different action-dependent branch sequences."""

from decimal import Decimal
from uuid import uuid4

import pytest

from open_commerce.simulator.engine import advance_state, compare_to_baseline, create_initial_state
from open_commerce.simulator.models import ENGINE_VERSION, PAIRED_ENGINE_VERSION
from open_commerce.simulator.randomness import KeyedExogenous
from open_commerce.simulator.scenarios import get_scenario


def test_keyed_draws_do_not_depend_on_consumption_or_other_actions() -> None:
    left = KeyedExogenous(11, "2026-09-01")
    right = KeyedExogenous(11, "2026-09-01")
    expected = left.draw("purchase", channel="organic", session=90, product="p1")
    for i in range(500):
        right.draw("click", channel="paid", session=i, product="p2")
    assert expected == right.draw("purchase", channel="organic", session=90, product="p1")
    assert expected != right.draw("cart", channel="organic", session=90, product="p1")
    assert expected != KeyedExogenous(101, "2026-09-01").draw(
        "purchase", channel="organic", session=90, product="p1"
    )


def test_engine_shared_session_draws_align_despite_campaign_and_purchase_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = get_scenario("acquisition_v1")
    left = create_initial_state(
        definition=definition, tenant_id=uuid4(), seed=11, paired_exogenous=True
    )
    right = left.model_copy(deep=True)
    right.campaigns[0].daily_budget_minor //= 2
    for product in right.products:
        for variant in product.variants:
            variant.price_minor *= 2
    traces: list[dict[tuple[object, ...], float]] = [{}, {}]
    arm = 0
    original = KeyedExogenous.draw

    def traced(
        self: KeyedExogenous,
        purpose: str,
        *,
        channel: str = "",
        campaign: str | None = None,
        session: int = 0,
        product: str = "",
    ) -> float:
        value = original(
            self, purpose, channel=channel, campaign=campaign, session=session, product=product
        )
        key = (self.seed, self.day, channel, campaign, session, product, purpose)
        traces[arm][key] = value
        return value

    monkeypatch.setattr(KeyedExogenous, "draw", traced)
    advance_state(state=left, definition=definition, hours=24)
    arm = 1
    advance_state(state=right, definition=definition, hours=24)
    shared = traces[0].keys() & traces[1].keys()
    assert len(shared) > 1000
    assert all(traces[0][key] == traces[1][key] for key in shared)
    assert traces[0].keys() != traces[1].keys()
    assert left.metrics[-1].sessions != right.metrics[-1].sessions
    assert left.metrics[-1].orders != right.metrics[-1].orders
    assert left.engine_version == PAIRED_ENGINE_VERSION
    assert left.metrics[-1].contribution_margin_rate <= Decimal(1)


def test_legacy_default_unchanged_and_paired_fixture_baseline_cannot_be_substituted() -> None:
    definition = get_scenario("acquisition_v1")
    legacy = create_initial_state(definition=definition, tenant_id=uuid4(), seed=11)
    paired = create_initial_state(
        definition=definition, tenant_id=uuid4(), seed=11, paired_exogenous=True
    )
    assert legacy.engine_version == ENGINE_VERSION
    assert paired.state_hash != legacy.state_hash
    with pytest.raises(ValueError, match="matched fixture"):
        compare_to_baseline(state=paired, definition=definition)
