"""Shared tenant resolution for multi-tenant serving.

Both the dashboard (read path) and the tracker (write/ingestion path) must agree
on *where a tenant's data lives*. They are mounted as separate FastAPI apps and
are each optional installs, so this neutral module -- depending on neither -- is
the single source of truth for tenant -> location resolution.

A tenant resolves to one of:
- a :class:`LibsqlTenant` spec (served from a libSQL/Turso database), or
- a filesystem data directory (the single-tenant default, or a per-tenant dir).

Artifact *bytes* (model snapshots, configs, …) are a separate location from the
metrics/metadata database. Remote libSQL tenants (a ``database`` URL) do not
store them locally — object storage comes later. Local libSQL tenants pin them
under ``base_dir``; filesystem tenants use :func:`resolve_data_dir`.

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
from aspara.utils.validators import validate_name

# Request header carrying the tenant id. A real deployment may derive the tenant
# from a subdomain or a JWT claim instead; this header is the minimal seam.
TENANT_HEADER = "X-Aspara-Tenant"

# Browser-friendly fallbacks so a normal page load (which cannot set custom
# headers) can still select a tenant. ``?tenant=lib`` also sets the cookie so
# subsequent same-origin fetches and clicks stay on that tenant.
TENANT_QUERY_PARAM = "tenant"
TENANT_COOKIE = "aspara_tenant"

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

    def __post_init__(self) -> None:
        if not (self.base_dir or "").strip() and not (self.database or "").strip():
            raise ValueError("LibsqlTenant requires base_dir (local) or database (remote)")

    def is_remote(self) -> bool:
        """True when this tenant is served from a remote libSQL URL (Turso, sqld, …)."""
        return bool((self.database or "").strip())


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


def resolve_artifact_base_dir(tenant_id: str) -> Path | None:
    """Return the local filesystem root for a tenant's artifact *bytes*, or None.

    Remote libSQL tenants keep metrics and metadata in the tenant database.
    Artifact bytes are not written to a shared local data directory in the
    meantime (they will go to object storage later). Local libSQL tenants
    (``base_dir`` only) pin bytes under that directory. Filesystem tenants use
    :func:`resolve_data_dir`.
    """
    spec = resolve_libsql_tenant(tenant_id)
    if spec is not None:
        if spec.is_remote():
            return None
        if spec.base_dir:
            return Path(spec.base_dir)
        return None
    return resolve_data_dir(tenant_id)


def safe_tenant_id(value: str | None) -> str | None:
    """Return ``value`` if it is a safe tenant id, otherwise None."""
    if not value:
        return None
    try:
        validate_name(value, "tenant")
    except ValueError:
        return None
    return value


def tenant_id_from_request(
    headers: Mapping[str, str],
    *,
    query: Mapping[str, str] | None = None,
    cookies: Mapping[str, str] | None = None,
) -> str:
    """Resolve the tenant id: header, then ``?tenant=``, then cookie, then default.

    The header remains the primary seam (APIs, curl). Query and cookie exist so a
    browser can open the dashboard without a header-injecting extension.
    """
    candidates = (
        headers.get(TENANT_HEADER),
        (query or {}).get(TENANT_QUERY_PARAM),
        (cookies or {}).get(TENANT_COOKIE),
    )
    for candidate in candidates:
        tenant = safe_tenant_id(candidate)
        if tenant is not None:
            return tenant
    return DEFAULT_TENANT


def tenant_id_from_headers(headers: Mapping[str, str]) -> str:
    """Read the tenant id from request headers, defaulting to DEFAULT_TENANT."""
    return tenant_id_from_request(headers)
