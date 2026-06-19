import importlib
import pkgutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter

import app.features as features_pkg


@dataclass(frozen=True)
class FeatureModule:
    """Descriptor a feature package exposes as ``feature`` in its __init__.

    Surfaces are implicit: whichever routers are provided get mounted.
    - ``api_router``   -> mounted under /api/v1   (REST/JSON)
    - ``ssr_router``   -> mounted at root         (SSR/HTML)
    - ``admin_views``  -> registered with SQLAdmin
    - ``tasks``/``cron`` -> registered with the arq worker
    """

    name: str
    api_router: APIRouter | None = None
    ssr_router: APIRouter | None = None
    admin_views: Sequence[type] = field(default_factory=tuple)
    tasks: Sequence[Callable[..., Any]] = field(default_factory=tuple)
    cron: Sequence[Any] = field(default_factory=tuple)


def discover_features() -> list[FeatureModule]:
    """Import every package under app.features and collect its ``feature``."""
    found: list[FeatureModule] = []
    for module_info in pkgutil.iter_modules(features_pkg.__path__):
        if not module_info.ispkg:
            continue
        module = importlib.import_module(f"{features_pkg.__name__}.{module_info.name}")
        feature = getattr(module, "feature", None)
        if isinstance(feature, FeatureModule):
            found.append(feature)
    return sorted(found, key=lambda f: f.name)
