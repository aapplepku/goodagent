"""Bounded product-propensity reranking after authoritative search eligibility."""

from decimal import Decimal

from open_commerce.ranking.models import RankingArtifact
from open_commerce.search.models import RankedCandidate, SearchIntent


def rerank(
    results: list[RankedCandidate], artifact: RankingArtifact, intent: SearchIntent
) -> list[RankedCandidate]:
    if intent.sort_preference != "relevance":
        return results
    ranked = []
    for result in results:
        item = result.model_copy(deep=True)
        if (
            all(item.constraint_matches.values())
            and item.score_components.relevance >= Decimal("0.20")
            and not item.score_components.exact_identifier
        ):
            # At most ten percent of the candidate's base score, never a fixed boost
            # that could overwhelm the much smaller RRF score range.
            boost = (
                max(Decimal("0"), item.score)
                * Decimal("0.10")
                * Decimal(str(artifact.scores.get(item.product_id, 0)))
            ).quantize(Decimal("0.000001"))
            item.score += boost
            item.score_components.engagement_boost = boost
            item.score_components.final = item.score
        ranked.append(item)
    return sorted(
        ranked,
        key=lambda item: (
            -int(item.score_components.exact_identifier),
            -item.score,
            item.product_id,
        ),
    )
