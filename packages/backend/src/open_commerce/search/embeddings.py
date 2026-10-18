"""Deterministic local embedding and sparse-vector providers."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from open_commerce.search.models import SparseVectorData

TOKEN_RE = re.compile(r"[a-z0-9]+")
IDENTIFIER_RE = re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+){2,}\b")
SPARSE_MODULUS = 65_521
SPARSE_MODEL = "hashed-tf-idf-identifier-v2"


def tokenize(text: str) -> list[str]:
    """Tokenize text deterministically for local search."""

    return TOKEN_RE.findall(text.lower())


class LocalHashEmbeddingProvider:
    """Small deterministic local embedding provider for CI and demos."""

    model_id = "local-hash-embedding-v1"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents."""

        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        """Embed one query."""

        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0 for _ in range(self.dimensions)]
        for token in semantic_tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
            for character in _token_character_features(token):
                char_digest = hashlib.sha256(f"char:{character}".encode()).digest()
                char_index = int.from_bytes(char_digest[:4], "big") % self.dimensions
                vector[char_index] += 0.15
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 8) for value in vector]


def sparse_vector(text: str) -> SparseVectorData:
    """Create a hashed sparse lexical vector."""

    counts = Counter(tokenize(text) + IDENTIFIER_RE.findall(text.lower()))
    total = sum(counts.values()) or 1
    weights: dict[int, float] = {}
    for token, count in counts.items():
        index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % SPARSE_MODULUS
        value = 1.0 + math.log(1 + count / total)
        weights[index] = weights.get(index, 0.0) + value
    items = [(index, round(value, 8)) for index, value in sorted(weights.items())]
    return SparseVectorData(
        indices=[index for index, _ in items],
        values=[value for _, value in items],
    )


def sparse_dot(left: SparseVectorData, right: SparseVectorData) -> float:
    """Return sparse dot product."""

    right_map = dict(zip(right.indices, right.values, strict=True))
    return sum(
        value * right_map.get(index, 0.0)
        for index, value in zip(left.indices, left.values, strict=True)
    )


def cosine(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for normalized or unnormalized vectors."""

    if len(left) != len(right):
        raise ValueError("vectors must have equal dimensions")
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _token_character_features(token: str) -> list[str]:
    if len(token) <= 3:
        return [token]
    return [token[index : index + 3] for index in range(len(token) - 2)]


def semantic_tokens(text: str) -> list[str]:
    tokens = tokenize(text)
    expansions = {
        "hiking": ["outdoor", "trail", "camp", "summit"],
        "hike": ["outdoor", "trail", "camp", "summit"],
        "running": ["footwear", "runner", "cushion"],
        "runner": ["footwear", "running", "cushion"],
        "kitchen": ["home", "ceramic", "storage"],
        "workspace": ["home", "electronics", "creator"],
        "headphones": ["electronics", "wireless", "portable"],
        "wireless": ["electronics", "portable", "smart"],
        "rain": ["weatherproof", "outdoor", "trail"],
        "waterproof": ["weatherproof", "outdoor", "trail"],
    }
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(expansions.get(token, []))
    return expanded
