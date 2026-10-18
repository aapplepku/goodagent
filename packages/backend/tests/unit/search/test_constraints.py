"""Explicit constraints cannot be relaxed or interpreted as provider field paths."""

import pytest
from pydantic import ValidationError

from open_commerce.search.errors import SearchConstraintsError
from open_commerce.search.models import ProductFilters
from open_commerce.search.parser import parse_search_intent


def test_currency_cents_and_exclusions_survive_explicit_filter_merge() -> None:
    intent = parse_search_intent(
        "outdoor under $12.34 without insulation",
        ProductFilters(
            max_price_minor=999999,
            excluded_attributes={"text": ["cotton"]},
        ),
    )
    assert intent.required_filters.max_price_minor == 1234
    assert intent.required_filters.excluded_attributes == {"text": ["cotton", "insulation"]}


def test_conflicting_price_range_is_rejected_instead_of_relaxed() -> None:
    with pytest.raises(SearchConstraintsError):
        parse_search_intent("under $10", ProductFilters(min_price_minor=1001))


@pytest.mark.parametrize("key", ["tenant_id.value", "variants[].stock", "../tenant", "$or"])
def test_attribute_names_cannot_inject_filter_paths(key: str) -> None:
    with pytest.raises(ValidationError):
        ProductFilters(attributes={key: ["anything"]})
