"""Deterministic random stream helpers for simulator scenarios."""

from __future__ import annotations

import hashlib
import json
import random


def derive_seed(root_seed: int, stream_name: str) -> int:
    """Derive a stable integer seed for a named child stream."""

    payload = f"{root_seed}:{stream_name}".encode()
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


class RandomStreams:
    """Factory for named RNG streams derived from one root seed."""

    def __init__(self, root_seed: int) -> None:
        self.root_seed = root_seed

    def rng(self, stream_name: str) -> random.Random:
        """Return an independent deterministic RNG for the given stream."""

        return random.Random(derive_seed(self.root_seed, stream_name))


class KeyedExogenous:
    """Capability-evaluation-only draws, independent of branch/loop consumption."""

    def __init__(self, seed: int, day: str, *, namespace: str = "capability-v1") -> None:
        self.seed = seed
        self.day = day
        self.namespace = namespace

    def draw(
        self,
        purpose: str,
        *,
        channel: str = "",
        campaign: str | None = None,
        session: int = 0,
        product: str = "",
    ) -> float:
        payload = json.dumps(
            [self.namespace, self.seed, self.day, channel, campaign, session, product, purpose],
            separators=(",", ":"),
        ).encode()
        value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        return value / (1 << 64)
