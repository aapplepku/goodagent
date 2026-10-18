"""Exercise native-output validation without loading/downloading a model."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from open_commerce.search.learned_embeddings import MiniLMEmbeddingProvider


def fake_provider() -> MiniLMEmbeddingProvider:
    provider = object.__new__(MiniLMEmbeddingProvider)
    provider._lock = asyncio.Lock()
    provider.tokenizer = Mock()
    provider.tokenizer.encode_batch.side_effect = lambda texts: [
        SimpleNamespace(ids=[1, 2, 0], attention_mask=[1, 1, 0], type_ids=[0, 0, 0]) for _ in texts
    ]
    provider.session = Mock()
    provider.session.run.side_effect = lambda _, feeds: [
        np.ones((*feeds["attention_mask"].shape, 384), dtype=np.float32)
    ]
    return provider


@pytest.mark.parametrize("value", [0.0, 1e-20, float("nan"), float("inf"), 1e30])
def test_unusable_native_output_is_rejected(value: float) -> None:
    provider = fake_provider()
    provider.session.run.side_effect = None
    provider.session.run.return_value = [np.full((1, 3, 384), value, dtype=np.float32)]

    with pytest.raises(ValueError, match="invalid learned embedding"):
        provider._embed(["synthetic product"])


@pytest.mark.parametrize("shape", [(1, 3, 383), (1, 384), (2, 3, 384), (1, 2, 384)])
def test_wrong_native_output_shape_is_rejected(shape: tuple[int, ...]) -> None:
    provider = fake_provider()
    provider.session.run.side_effect = None
    provider.session.run.return_value = [np.ones(shape, dtype=np.float32)]

    with pytest.raises(ValueError, match="invalid learned embedding output"):
        provider._embed(["synthetic product"])


def test_any_zero_vector_fails_the_entire_batch() -> None:
    provider = fake_provider()
    tokens = np.ones((2, 3, 384), dtype=np.float32)
    tokens[1] = 0
    provider.session.run.side_effect = None
    provider.session.run.return_value = [tokens]

    with pytest.raises(ValueError, match="invalid learned embedding norm"):
        provider._embed(["valid product", "invalid product"])


def test_cancelling_token_vectors_are_rejected_after_pooling() -> None:
    provider = fake_provider()
    tokens = np.ones((1, 3, 384), dtype=np.float32)
    tokens[0, 1] = -1
    provider.session.run.side_effect = None
    provider.session.run.return_value = [tokens]

    with pytest.raises(ValueError, match="invalid learned embedding norm"):
        provider._embed(["synthetic product"])


def test_masked_pooling_yields_nonzero_unit_vector() -> None:
    provider = fake_provider()
    tokens = np.zeros((1, 3, 384), dtype=np.float32)
    tokens[0, 0, 0] = 6
    tokens[0, 1, 1] = 8
    tokens[0, 2, 2] = 1000  # Padding must not influence pooling.
    provider.session.run.side_effect = None
    provider.session.run.return_value = [tokens]

    vector = provider._embed(["synthetic product"])[0]

    assert vector[:3] == pytest.approx([0.6, 0.8, 0.0])
    assert np.linalg.norm(vector) == pytest.approx(1.0)
    assert all(value == 0.0 for value in vector[2:])


async def test_document_batches_and_query_use_identical_validation() -> None:
    provider = fake_provider()
    documents = await provider.embed_documents(["synthetic product"] * 17)
    query = await provider.embed_query("synthetic product")

    assert len(documents) == 17
    assert provider.session.run.call_count == 3
    assert isinstance(provider.tokenizer, Mock)
    assert [len(call.args[0]) for call in provider.tokenizer.encode_batch.call_args_list] == [
        16,
        1,
        1,
    ]
    for vector in documents:
        assert vector == pytest.approx(query)
        assert len(vector) == 384
        assert np.linalg.norm(vector) == pytest.approx(1.0)


async def test_empty_input_does_not_invoke_native_runtime() -> None:
    provider = fake_provider()
    assert await provider.embed_documents([]) == []
    provider.session.run.assert_not_called()


async def test_input_bounds_fail_before_native_runtime() -> None:
    provider = fake_provider()
    for texts in [["x" * 20_001], ["x"] * 10_001]:
        with pytest.raises(ValueError, match="bounded catalog input"):
            await provider.embed_documents(texts)
    provider.session.run.assert_not_called()
