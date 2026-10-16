"""Dataset loaders for bhasha_lib."""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy-load modules to avoid runpy warnings when running modules with -m."""
    if name == "load_aksharantar":
        from bhasha_lib.loaders.aksharantar import load_aksharantar

        return load_aksharantar
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["load_aksharantar"]
