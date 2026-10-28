"""Aura platform API: tenant onboarding and lifecycle for the Aura OpenStack cloud."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aura-api")
except PackageNotFoundError:  # pragma: no cover - only when running from a bare source tree
    __version__ = "0.0.0"
