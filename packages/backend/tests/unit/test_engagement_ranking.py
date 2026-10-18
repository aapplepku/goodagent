"""Real fitting, temporal isolation, target grounding and hard serving constraints."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest

from open_commerce.core.types import canonical_hash
from open_commerce.ranking.engagement import normalize_engagement
from open_commerce.ranking.models import EngagementEvent, RankingDataError, TrainRankingInput
from open_commerce.ranking.training import train, validate_goal


def evidence() -> list[EngagementEvent]:
    events = []
    for i in range(600):
        product = "high" if i % 2 else "low"
        at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=i)
        kinds = ["product_view"]
        if (product == "high" and i % 10 != 1) or (product == "low" and i % 20 == 0):
            kinds.extend(["add_to_cart", "purchase"])
        for j, kind in enumerate(kinds):
            events.append(
                EngagementEvent.model_validate(
                    {
                        "key": sha256(f"{i}:{j}".encode()).hexdigest(),
                        "product_id": product,
                        "session": sha256(str(i).encode()).hexdigest(),
                        "kind": kind,
                        "at": at + timedelta(minutes=j),
                    }
                )
            )
    return sorted(events, key=lambda item: (item.at, item.key))


def test_logistic_is_a_real_reproducible_fit_with_temporal_evaluation() -> None:
    request = TrainRankingInput(
        goal="Increase purchases from search", target="purchase", method="logistic_regression"
    )
    artifact, metrics = train(evidence(), ["high", "low"], request)
    again, _ = train(evidence(), ["low", "high"], request)
    assert canonical_hash(artifact) == canonical_hash(again)
    assert artifact.coefficients and any(abs(value) > 0.01 for value in artifact.coefficients)
    assert artifact.scores["high"] > artifact.scores["low"]
    assert metrics["eligible_for_activation"] is True
    assert float(metrics["heldout_roc_auc"]) > 0.7  # type: ignore[arg-type]
    assert artifact.feature_cutoff < artifact.evaluation_cutoff
    changed = [
        event.model_copy(update={"kind": "add_to_cart"})
        if event.at > artifact.evaluation_cutoff
        and event.kind == "purchase"
        and int(event.key[0], 16) < 5
        else event
        for event in evidence()
    ]
    changed_artifact, changed_metrics = train(changed, ["high", "low"], request)
    assert changed_artifact.coefficients == artifact.coefficients
    assert changed_artifact.scores == artifact.scores
    assert changed_metrics["test_positives"] != metrics["test_positives"]


def test_popularity_uses_only_earlier_events() -> None:
    artifact, metrics = train(
        evidence(),
        ["high", "low"],
        TrainRankingInput(goal="Rank by popular purchases", target="purchase", method="popularity"),
    )
    assert artifact.scores["high"] > artifact.scores["low"]
    assert "heldout_ndcg_at_10" in metrics
    assert artifact.coefficients == []


@pytest.mark.parametrize(
    "goal,target",
    [
        ("Improve our store", "click"),
        ("Increase profit from sales", "purchase"),
        ("Improve clicks", "purchase"),
    ],
)
def test_unsupported_or_ungrounded_targets_require_clarification(goal: str, target: str) -> None:
    with pytest.raises(RankingDataError):
        validate_goal(
            TrainRankingInput.model_validate(
                {"goal": goal, "target": target, "method": "logistic_regression"}
            )
        )


def test_no_invented_click_impressions_or_cross_catalog_training() -> None:
    with pytest.raises(RankingDataError, match="impression"):
        train(
            evidence(),
            ["high", "low"],
            TrainRankingInput(goal="Increase clicks", target="click", method="logistic_regression"),
        )
    with pytest.raises(RankingDataError, match="match the active catalog"):
        train(
            evidence(),
            ["other"],
            TrainRankingInput(goal="Increase purchases", target="purchase", method="popularity"),
        )


def test_ingestion_discards_raw_identifiers_queries_and_deduplicates() -> None:
    csv = (
        "event_id,event_type,occurred_at,product_id,session_id,query,anonymous_id\n"
        "e1,product_view,2026-01-01T01:00:00Z,p1,sensitive-session,private query,visitor1\n"
    )
    events = normalize_engagement(UUID(int=1), csv + csv.splitlines()[-1] + "\n")
    assert normalize_engagement(UUID(int=1), "\ufeff" + csv) == events
    assert len(events) == 1
    assert "sensitive-session" not in events[0].model_dump_json()
    assert "private query" not in events[0].model_dump_json()
    assert events[0].session != normalize_engagement(UUID(int=2), csv)[0].session
    with pytest.raises(RankingDataError, match="conflicting"):
        normalize_engagement(UUID(int=1), csv + csv.splitlines()[-1].replace("p1", "p2") + "\n")
    with pytest.raises(RankingDataError, match="timezone"):
        normalize_engagement(UUID(int=1), csv.replace("01:00:00Z", "01:00:00"))
    with pytest.raises(RankingDataError, match="Unsupported event"):
        normalize_engagement(UUID(int=1), csv.replace("product_view", "execute_sql"))


def test_empty_single_class_data_cannot_produce_a_classifier() -> None:
    with pytest.raises(RankingDataError):
        train(
            [event for event in evidence() if event.kind == "product_view"],
            ["high", "low"],
            TrainRankingInput(
                goal="Increase purchases", target="purchase", method="logistic_regression"
            ),
        )
