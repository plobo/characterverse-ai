"""Provider-neutral AI interfaces (plan §7.1) and the default local, deterministic adapters.

Every adapter exposes ProviderInfo (name/version, terms URL, cost + latency metadata, availability) so usage
can be recorded per job. Hosted adapters are optional and must not be enabled until their licence/terms
have a reviewed record in docs/ASSET_AND_MODEL_LICENSES.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    version: str
    kind: str
    terms_url: str | None
    cost_per_call_usd: float
    typical_latency_ms: int
    local: bool
    available: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TextGenerationProvider(Protocol):
    info: ProviderInfo

    def character_recipe(self, description: str, hints: dict[str, Any], vocab: dict[str, Any]) -> dict[str, Any]: ...
    def fusion_suggestions(self, names: list[str], traits: list[str]) -> list[dict[str, str]]: ...
    def storyboard(self, request: dict[str, Any], vocab: dict[str, Any]) -> dict[str, Any]: ...


class ImageGenerationProvider(Protocol):
    info: ProviderInfo

    def thumbnail(self, parts: list[dict[str, Any]], size: int) -> bytes: ...


class SpeechGenerationProvider(Protocol):
    info: ProviderInfo

    def synthesize(self, text: str, voice: dict[str, Any], sample_rate: int) -> Any: ...


class ContentModerationProvider(Protocol):
    name: str
    version: str

    def score(self, text: str) -> tuple[float, list[str]]: ...


class EmbeddingProvider(Protocol):  # optional, not used by the MVP
    info: ProviderInfo

    def embed(self, text: str) -> list[float]: ...


def stable_int(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16)
