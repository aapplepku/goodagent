"""Reproducible CPU ranking with chronological, non-overlapping evidence windows."""

import math
import re
import warnings
from collections import Counter, defaultdict
from datetime import timedelta

from open_commerce.ranking.models import (
    EngagementEvent,
    RankingArtifact,
    RankingDataError,
    TrainRankingInput,
)

ATTRIBUTION = timedelta(minutes=30)
FEATURES = ["log_views", "cart_rate", "purchase_rate", "click_rate"]


def validate_goal(request: TrainRankingInput) -> None:
    terms = {
        "purchase": r"\b(purchases?|sales|orders?|conversions?|buying)\b",
        "add_to_cart": r"\b(carts?|baskets?)\b",
        "click": r"\b(clicks?|ctr|clickthrough)\b",
        "product_view": r"\b(views?|popular|popularity|browsing)\b",
    }
    if not re.search(terms[request.target], request.goal, re.I):
        raise RankingDataError(
            "Clarify the target: product views, clicks, cart additions or purchases."
        )
    if re.search(r"\b(profit|margin|revenue|retention|lifetime)\b", request.goal, re.I):
        raise RankingDataError(
            "This ranker predicts event frequency, not profit or revenue. "
            "Confirm an event proxy first."
        )
    if request.method == "logistic_regression" and request.target == "product_view":
        raise RankingDataError(
            "Use popularity for views, or choose clicks, cart additions or purchases "
            "for logistic regression."
        )


def train(
    events: list[EngagementEvent], product_ids: list[str], request: TrainRankingInput
) -> tuple[RankingArtifact, dict[str, float | int | str | bool | None]]:
    validate_goal(request)
    products = sorted(set(product_ids))
    if not events or not products:
        raise RankingDataError("Upload engagement and publish a catalog before training.")
    unknown = {event.product_id for event in events} - set(products)
    if unknown:
        raise RankingDataError(
            f"{len(unknown)} engagement product IDs do not match the active catalog. "
            "Upload matching data."
        )
    ordered = sorted(events, key=lambda event: (event.at, event.key))
    times = sorted({event.at for event in ordered})
    if len(times) < 10 or len(events) < 40:
        raise RankingDataError(
            "At least 40 events across 10 timestamps are required for a temporal evaluation."
        )
    test_start = times[int(len(times) * 0.7)]
    if request.method == "popularity":
        counts = Counter(
            event.product_id
            for event in ordered
            if event.at < test_start and event.kind == request.target
        )
        held = Counter(
            event.product_id
            for event in ordered
            if event.at >= test_start and event.kind == request.target
        )
        if sum(counts.values()) < 20 or sum(held.values()) < 5 or len(counts) < 2:
            raise RankingDataError(
                "Popularity needs at least 20 earlier and 5 held-out target events "
                "across multiple products."
            )
        maximum = max(counts.values())
        scores = {
            product: math.log1p(counts[product]) / math.log1p(maximum) for product in products
        }
        metric = ndcg(sorted(products, key=lambda product: (-scores[product], product)), held)
        baseline = ndcg(products, held)
        artifact = RankingArtifact(
            method=request.method,
            target=request.target,
            features=["log_target_count"],
            coefficients=[],
            intercept=0,
            scores=scores,
            feature_cutoff=test_start,
            evaluation_cutoff=test_start,
            library="python-log-count-v1",
        )
        return artifact, {
            "train_events": sum(counts.values()),
            "test_events": sum(held.values()),
            "heldout_ndcg_at_10": metric,
            "alphabetical_ndcg_at_10": baseline,
            "eligible_for_activation": metric >= baseline,
            "evaluation": "Temporal event-count ranking; not query relevance or causal lift",
            "feature_cutoff": test_start.isoformat(),
            "test_start": test_start.isoformat(),
        }

    # Fit features on an earlier warm-up window, not the labels used for fitting/evaluation.
    feature_cutoff = times[int(len(times) * 0.3)]
    history = [event for event in ordered if event.at < feature_cutoff]
    features = historical_features(history, products)
    exposure = "impression" if request.target == "click" else "product_view"
    if any(event.session is None for event in ordered if event.kind in {exposure, request.target}):
        raise RankingDataError(
            "Logistic regression needs session_id on exposures and target events; "
            "anonymous_id is not a session."
        )
    grouped: dict[tuple[str, str], list[EngagementEvent]] = defaultdict(list)
    for event in ordered:
        if event.session:
            grouped[(event.session, event.product_id)].append(event)
    train_rows: list[tuple[str, int]] = []
    test_rows: list[tuple[str, int]] = []
    discarded = 0
    for (_, product), group in grouped.items():
        exposures = [event for event in group if event.kind == exposure]
        if not exposures:
            continue
        first = exposures[0].at
        end = first + ATTRIBUTION
        # Whole session/product groups belong to one partition. Boundary and right-censored
        # observations are dropped, never relabeled as negatives.
        if group[0].at >= feature_cutoff and group[-1].at < test_start and end < test_start:
            partition = train_rows
        elif group[0].at >= test_start and end <= times[-1]:
            partition = test_rows
        else:
            discarded += 1
            continue
        label = int(
            any(event.kind == request.target and first < event.at <= end for event in group)
        )
        partition.append((product, label))
    partitions = ((train_rows, 40, "training"), (test_rows, 20, "held-out"))
    for rows, minimum, partition_name in partitions:
        positives = sum(target for _, target in rows)
        if len(rows) < minimum or min(positives, len(rows) - positives) < 5:
            raise RankingDataError(
                f"The {partition_name} partition needs {minimum} mature {exposure} sessions "
                "with at least 5 positives and 5 negatives."
            )
    from sklearn import __version__
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss, roc_auc_score

    x = [features[product] for product, _ in train_rows]
    y = [label for _, label in train_rows]
    estimator = LogisticRegression(C=1.0, solver="lbfgs", max_iter=500, random_state=42)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            estimator.fit(x, y)
        except ConvergenceWarning as exc:
            raise RankingDataError(
                "The logistic fit did not converge; no serving artifact was published."
            ) from exc
    probabilities = estimator.predict_proba([features[product] for product, _ in test_rows])[:, 1]
    test_y = [label for _, label in test_rows]
    constant = sum(y) / len(y)
    loss = float(log_loss(test_y, probabilities, labels=[0, 1]))
    baseline_loss = float(log_loss(test_y, [constant] * len(test_y), labels=[0, 1]))
    scores = estimator.predict_proba([features[product] for product in products])[:, 1]
    artifact = RankingArtifact(
        method=request.method,
        target=request.target,
        features=FEATURES,
        coefficients=[float(value) for value in estimator.coef_[0]],
        intercept=float(estimator.intercept_[0]),
        scores={product: float(score) for product, score in zip(products, scores, strict=True)},
        feature_cutoff=feature_cutoff,
        evaluation_cutoff=test_start,
        library=f"scikit-learn-{__version__}",
    )
    return artifact, {
        "train_samples": len(y),
        "train_positives": sum(y),
        "test_samples": len(test_y),
        "test_positives": sum(test_y),
        "heldout_log_loss": loss,
        "constant_log_loss": baseline_loss,
        "heldout_roc_auc": float(roc_auc_score(test_y, probabilities)),
        "eligible_for_activation": loss <= baseline_loss,
        "boundary_groups_dropped": discarded,
        "exposure": exposure,
        "attribution_minutes": 30,
        "feature_cutoff": feature_cutoff.isoformat(),
        "test_start": test_start.isoformat(),
        "evaluation": "Temporal product propensity; exposure-biased, not causal or personalized",
    }


def historical_features(
    events: list[EngagementEvent], products: list[str]
) -> dict[str, list[float]]:
    counts = Counter((event.product_id, event.kind) for event in events)
    result = {}
    for product in products:
        views = counts[product, "product_view"]
        impressions = counts[product, "impression"]
        result[product] = [
            math.log1p(views) / 10,
            min(1.0, (counts[product, "add_to_cart"] + 1) / (views + 10)),
            min(1.0, (counts[product, "purchase"] + 1) / (views + 10)),
            min(1.0, (counts[product, "click"] + 1) / (impressions + 10)),
        ]
    return result


def ndcg(order: list[str], relevance: Counter[str]) -> float:
    def dcg(values: list[int]) -> float:
        return sum(value / math.log2(index + 2) for index, value in enumerate(values[:10]))

    ideal = dcg(sorted(relevance.values(), reverse=True))
    return dcg([relevance[product] for product in order]) / ideal if ideal else 0.0
