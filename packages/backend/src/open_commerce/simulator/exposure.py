"""Deterministic simulator exposure/ranking policy."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from open_commerce.simulator.models import Exposure, ProductState, SearchBoostState


class ExposurePolicy(Protocol):
    """Interface search/recommendation milestone can replace."""

    def rank(
        self,
        *,
        query_text: str,
        category: str,
        products: list[ProductState],
        boosts: list[SearchBoostState],
        at: datetime,
        limit: int,
    ) -> list[Exposure]:
        """Rank product exposures for one shopper intent."""


class DefaultExposurePolicy:
    """Lexical/category/popularity ranking with a relevance floor for boosts."""

    def rank(
        self,
        *,
        query_text: str,
        category: str,
        products: list[ProductState],
        boosts: list[SearchBoostState],
        at: datetime,
        limit: int,
    ) -> list[Exposure]:
        scored: list[tuple[Decimal, Decimal, str]] = []
        tokens = [token for token in query_text.lower().split() if token]
        for product in products:
            if product.total_inventory <= 0:
                continue
            relevance = self._relevance(tokens=tokens, category=category, product=product)
            boost_multiplier = Decimal("1")
            for boost in boosts:
                if boost.applies_to(query_text, product, at):
                    if relevance >= Decimal("0.30"):
                        boost_multiplier = max(boost_multiplier, boost.multiplier)
            score = relevance * boost_multiplier + product.popularity_score * Decimal("0.20")
            scored.append((score, relevance, product.id))

        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [
            Exposure(product_id=product_id, score=score, relevance=relevance, position=index + 1)
            for index, (score, relevance, product_id) in enumerate(scored[:limit])
        ]

    @staticmethod
    def _relevance(*, tokens: list[str], category: str, product: ProductState) -> Decimal:
        text = " ".join(
            [
                product.title,
                product.category,
                product.description_text,
                " ".join(product.tags),
                " ".join(product.attributes.values()),
            ]
        ).lower()
        lexical_hits = sum(1 for token in tokens if token in text)
        lexical = Decimal(lexical_hits) / Decimal(max(1, len(tokens)))
        category_match = Decimal("1") if product.category == category else Decimal("0")
        quality = product.quality_score * Decimal("0.15")
        popularity = product.popularity_score * Decimal("0.15")
        return min(
            Decimal("1"),
            category_match * Decimal("0.55") + lexical * Decimal("0.30") + quality + popularity,
        )
