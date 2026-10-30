"""Turning text into vectors for search: Voyage AI in production, a hashing stand-in otherwise."""

import hashlib
import math
import re
from functools import lru_cache
from typing import Literal, Protocol

import httpx

from app.config import get_settings

DIMENSIONS = 1024
InputType = Literal["document", "query"]


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]: ...


class HashingEmbedder:
    """Words and their three-letter pieces, hashed into a vector. Needs no account or network.

    It finds shared words and spellings, not meaning, so it stands in for the real model in
    development and tests only.
    """

    model = "hashing-v1"

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            word = word.removesuffix("s") if len(word) > 3 else word
            features = [word] + [word[i : i + 3] for i in range(max(len(word) - 2, 0))]
            for feature in features:
                digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % DIMENSIONS
                vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class VoyageEmbedder:
    URL = "https://api.voyageai.com/v1/embeddings"
    BATCH = 128

    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None) -> None:
        self.model = model
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=30)

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH):
            response = self._client.post(
                self.URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "input": texts[start : start + self.BATCH],
                    "model": self.model,
                    "input_type": input_type,
                    "output_dimension": DIMENSIONS,
                },
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors.extend(item["embedding"] for item in data)
        return vectors


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    provider = settings.embedding_provider
    if provider == "auto":
        provider = "voyage" if settings.voyage_api_key else "hashing"
    if provider == "voyage":
        if not settings.voyage_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER is voyage but VOYAGE_API_KEY isn't set.")
        return VoyageEmbedder(settings.voyage_api_key, settings.embedding_model)
    return HashingEmbedder()
