"""Pinned MiniLM ONNX encoder. No download, remote code or LLM calls at runtime."""

import asyncio
import hashlib
import os
from functools import lru_cache
from pathlib import Path

MODEL_REPOSITORY = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "dfa9feb5cece5be2cc8fc23a3cf1f32473a9d56f"
MODEL_FILES = {
    "model.onnx": (
        "onnx/model.onnx",
        "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    ),
    "tokenizer.json": (
        "tokenizer.json",
        "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
    ),
}


def verified_model_files(directory: Path) -> dict[str, bytes]:
    """Only two allowlisted, immutable data files may reach native parsers."""
    result = {}
    for name, (_, expected) in MODEL_FILES.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000_000:
            raise ValueError("missing or invalid pinned search model artifact")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("pinned search model checksum mismatch")
        result[name] = data
    return result


class MiniLMEmbeddingProvider:
    """384 dimensions; attention-masked mean pooling and L2 normalization."""

    model_id = f"{MODEL_REPOSITORY}@{MODEL_REVISION}:onnx-fp32-mean-l2-v1"
    dimensions = 384

    def __init__(self, directory: Path) -> None:
        data = verified_model_files(directory)
        # POSIX ORT latches the full opt-out before constructing its native environment.
        os.environ["ORT_DISABLE_TELEMETRY"] = "1"
        import onnxruntime as ort
        from tokenizers import Tokenizer

        ort.disable_telemetry_events()
        self.tokenizer = Tokenizer.from_str(data["tokenizer.json"].decode("utf-8"))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.use_deterministic_compute = True
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            data["model.onnx"], sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.session.disable_fallback()
        self._lock = asyncio.Lock()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if any(len(text) > 20_000 for text in texts) or len(texts) > 10_000:
            raise ValueError("embedding request exceeds bounded catalog input")
        async with self._lock:
            return await asyncio.to_thread(self._embed, texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        vectors: list[list[float]] = []
        for offset in range(0, len(texts), 16):
            encoded = self.tokenizer.encode_batch(texts[offset : offset + 16])
            mask = np.asarray([item.attention_mask for item in encoded], dtype=np.int64)
            feeds = {
                "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
                "attention_mask": mask,
                "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64),
            }
            tokens = np.asarray(self.session.run(None, feeds)[0], dtype=np.float32)
            if tokens.shape != (*mask.shape, self.dimensions) or not np.isfinite(tokens).all():
                raise ValueError("invalid learned embedding output")
            weights = mask[:, :, None].astype(np.float32)
            with np.errstate(over="ignore", invalid="ignore"):
                pooled = (tokens * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1e-9)
                norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            if not np.isfinite(norms).all() or (norms <= 1e-9).any():
                raise ValueError("invalid learned embedding norm")
            normalized = pooled / norms
            if (
                normalized.shape != (len(encoded), self.dimensions)
                or not np.isfinite(normalized).all()
            ):
                raise ValueError("invalid learned embedding output")
            vectors.extend([[float(value) for value in row] for row in normalized])
        return vectors


@lru_cache(maxsize=1)
def get_minilm_provider(directory: Path) -> MiniLMEmbeddingProvider:
    """One immutable CPU session per configured process, not per shopper request."""
    return MiniLMEmbeddingProvider(directory)
