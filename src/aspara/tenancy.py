"""Shared tenant resolution for multi-tenant serving.

Both the dashboard (read path) and the tracker (write/ingestion path) must agree
on *where a tenant's data lives*. They are mounted as separate FastAPI apps and
are each optional installs, so this neutral module -- depending on neither -- is
the single source of truth for tenant -> location resolution.

A tenant resolves to one of:
- a :class:`LibsqlTenant` spec (served from a libSQL/Turso database), or
- a filesystem data directory (the single-tenant default, or a per-tenant dir).

Resolvers are process-global and installed once at startup via the
``configure_*`` functions. When no resolver is installed, every request maps to
the single configured (or default) data directory, i.e. behavior is identical to
the pre-multi-tenant server.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from aspara.config import get_data_dir

# Request header carrying the tenant id. A real deployment may derive the tenant
# from a subdomain or a JWT claim instead; this header is the minimal seam.
TENANT_HEADER = "X-Aspara-Tenant"

# Tenant id used when no tenant is resolved from the request (single-tenant default).
DEFAULT_TENANT = "default"


@dataclass(frozen=True)
class LibsqlTenant:
    """Connection spec for a libSQL-backed tenant.

    Either ``base_dir`` (a local ``{base_dir}/aspara.db`` file) or ``database``
    (a remote ``libsql://`` URL, with an optional ``auth_token``) identifies the
    tenant's single database.
    """

    base_dir: str | None = None
    database: str | None = None
    auth_token: str | None = None


# Mutable container for the single configured data directory (single-tenant default).
_custom_data_dir: list[str | None] = [None]

# Optional tenant resolver: tenant_id -> data directory. When unset, every request
# uses the single configured data directory.
_tenant_resolver: list[Callable[[str], str | Path] | None] = [None]

# Optional libSQL tenant resolver: tenant_id -> LibsqlTenant | None. When it returns
# a spec, that tenant is served from its libSQL database; returning None falls back
# to filesystem resolution, so file-based tenants are unaffected.
_libsql_resolver: list[Callable[[str], LibsqlTenant | None] | None] = [None]

# Callbacks fired whenever the resolver configuration changes. Consumers (e.g. the
# dashboard's catalog cache) register here to invalidate derived state.
_config_change_callbacks: list[Callable[[], None]] = []


def register_config_change_callback(callback: Callable[[], None]) -> None:
    """Register a callback fired before any resolver configuration change.

    Used by the dashboard to clear its cached catalog instances so a new resolver
    takes effect immediately.
    """
    if callback not in _config_change_callbacks:
        _config_change_callbacks.append(callback)


def _notify_config_change() -> None:
    for callback in _config_change_callbacks:
        callback()


def configure_data_dir(data_dir: str | None = None) -> None:
    """Configure the single (default-tenant) data directory.

    Args:
        data_dir: Custom data directory path. If None, uses the default.
    """
    _notify_config_change()
    _custom_data_dir[0] = data_dir


def configure_tenant_resolver(resolver: Callable[[str], str | Path] | None) -> None:
    """Install (or clear) the tenant -> data directory resolver.

    Passing None restores single-tenant behavior (the configured data directory).
    """
    _notify_config_change()
    _tenant_resolver[0] = resolver


def configure_libsql_tenant_resolver(resolver: Callable[[str], LibsqlTenant | None] | None) -> None:
    """Install (or clear) the tenant -> libSQL database resolver.

    When installed and it returns a :class:`LibsqlTenant` for a tenant, that tenant
    is served from its libSQL database. Returning None for a tenant (or passing None
    here) falls back to filesystem resolution, so file-based tenants are unaffected.
    """
    _notify_config_change()
    _libsql_resolver[0] = resolver


def resolve_libsql_tenant(tenant_id: str) -> LibsqlTenant | None:
    """Resolve a tenant id to its libSQL spec, or None for filesystem tenants."""
    resolver = _libsql_resolver[0]
    if resolver is not None:
        return resolver(tenant_id)
    return None


def resolve_data_dir(tenant_id: str) -> Path:
    """Resolve a tenant id to its filesystem data directory.

    Uses the configured tenant resolver when present; otherwise falls back to the
    single configured data directory (single-tenant behavior).
    """
    resolver = _tenant_resolver[0]
    if resolver is not None:
        return Path(resolver(tenant_id))
    if _custom_data_dir[0] is not None:
        return Path(_custom_data_dir[0])
    return Path(get_data_dir())


def tenant_id_from_headers(headers: Mapping[str, str]) -> str:
    """Read the tenant id from request headers, defaulting to DEFAULT_TENANT."""
    return headers.get(TENANT_HEADER) or DEFAULT_TENANT
