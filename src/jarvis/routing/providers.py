"""ProviderCatalog — laddar providers.yaml och exponerar leverantörsdata."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


CATALOG_PATH = Path(__file__).parent / "providers.yaml"


@dataclass
class ModelSpec:
    id: str
    class_: str
    quality_index: Optional[float]


@dataclass
class ProviderSpec:
    key: str
    display_name: str
    base_url: str
    api_key_env: str
    cost_per_1k_input_sek: float
    cost_per_1k_output_sek: float
    rate_limit_rpm: int
    latency_p50_ms: int
    trains_on_data: bool
    models: List[ModelSpec]
    enabled_env: Optional[str] = None
    sensitivity_max: str = "secret"

    def has_key(self) -> bool:
        return bool(os.environ.get(self.api_key_env, "")) and (
            not self.enabled_env or os.environ.get(self.enabled_env) == "1"
        )

    def get_model(self, model_id: str) -> Optional[ModelSpec]:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def estimate_cost_sek(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1000 * self.cost_per_1k_input_sek
            + output_tokens / 1000 * self.cost_per_1k_output_sek
        )


class ProviderCatalog:
    def __init__(self, path: Path = CATALOG_PATH):
        with open(path, encoding="utf-8") as fh:
            self.raw: Dict[str, Any] = yaml.safe_load(fh)
        self.providers: Dict[str, ProviderSpec] = {}
        for key, p in self.raw.get("providers", {}).items():
            self.providers[key] = ProviderSpec(
                key=key,
                display_name=p["display_name"],
                base_url=p["base_url"],
                api_key_env=p["api_key_env"],
                cost_per_1k_input_sek=float(p["cost_per_1k_input_sek"]),
                cost_per_1k_output_sek=float(p["cost_per_1k_output_sek"]),
                rate_limit_rpm=int(p["rate_limit_rpm"]),
                latency_p50_ms=int(p["latency_p50_ms"]),
                trains_on_data=bool(p.get("trains_on_data", False)),
                models=[
                    ModelSpec(id=m["id"], class_=m["class"],
                              quality_index=float(m["quality_index"])
                              if m.get("quality_index") is not None else None)
                    for m in p.get("models", [])
                ],
                enabled_env=p.get("enabled_env"),
                sensitivity_max=p.get("sensitivity_max", "secret"),
            )
        self.integration_status: Dict[str, str] = {}
        from .perplexity import configure_router
        configure_router(self)
        from .huggingface import configure_huggingface
        configure_huggingface(self)

    @property
    def tiers(self) -> Dict[str, Any]:
        return self.raw.get("tiers", {})

    @property
    def budget(self) -> Dict[str, Any]:
        return self.raw.get("budget", {})

    def get(self, key: str) -> ProviderSpec:
        return self.providers[key]
