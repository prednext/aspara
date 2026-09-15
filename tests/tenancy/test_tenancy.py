"""Unit tests for aspara.tenancy (tenant id parsing and LibsqlTenant specs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aspara.tenancy import (
    DEFAULT_TENANT,
    LibsqlTenant,
    configure_data_dir,
    configure_libsql_tenant_resolver,
    resolve_artifact_base_dir,
    tenant_id_from_request,
)


def test_libsql_tenant_requires_base_dir_or_database() -> None:
    with pytest.raises(ValueError, match="base_dir"):
        LibsqlTenant()
    with pytest.raises(ValueError, match="base_dir"):
        LibsqlTenant(base_dir="  ", database="")
    assert LibsqlTenant(base_dir="/tmp/t").base_dir == "/tmp/t"
    assert LibsqlTenant(database="libsql://example").database == "libsql://example"
    assert LibsqlTenant(base_dir="/tmp/t").is_remote() is False
    assert LibsqlTenant(database="libsql://example").is_remote() is True
    assert LibsqlTenant(base_dir="/tmp/t", database="libsql://example").is_remote() is True


def test_tenant_id_precedence_header_then_query_then_cookie() -> None:
    assert tenant_id_from_request({}) == DEFAULT_TENANT
    assert tenant_id_from_request({}, query={"tenant": "q"}, cookies={"aspara_tenant": "c"}) == "q"
    assert tenant_id_from_request({"X-Aspara-Tenant": "h"}, query={"tenant": "q"}) == "h"
    assert tenant_id_from_request({}, cookies={"aspara_tenant": "c"}) == "c"


def test_invalid_tenant_id_is_rejected() -> None:
    from aspara.tenancy import InvalidTenantIdError

    with pytest.raises(InvalidTenantIdError):
        tenant_id_from_request({}, query={"tenant": "../etc"})
    with pytest.raises(InvalidTenantIdError):
        tenant_id_from_request({"X-Aspara-Tenant": "my.tenant"})
    with pytest.raises(InvalidTenantIdError):
        tenant_id_from_request({}, cookies={"aspara_tenant": "../etc"})
    # A valid later source must not hide an invalid earlier one.
    with pytest.raises(InvalidTenantIdError):
        tenant_id_from_request({"X-Aspara-Tenant": "../etc"}, cookies={"aspara_tenant": "ok"})


def test_resolve_artifact_base_dir_skips_remote_libsql(tmp_path: Path) -> None:
    """Remote libSQL tenants have no local artifact root; local ones pin to base_dir."""
    local_dir = tmp_path / "local"
    shared = tmp_path / "shared"
    configure_data_dir(str(shared))
    configure_libsql_tenant_resolver(
        lambda t: {
            "local": LibsqlTenant(base_dir=str(local_dir)),
            "remote": LibsqlTenant(database="libsql://example"),
            "hybrid": LibsqlTenant(base_dir=str(local_dir), database="libsql://example"),
        }.get(t)
    )
    try:
        assert resolve_artifact_base_dir("local") == local_dir
        assert resolve_artifact_base_dir("remote") is None
        assert resolve_artifact_base_dir("hybrid") is None
        assert resolve_artifact_base_dir("fs") == shared
    finally:
        configure_libsql_tenant_resolver(None)
        configure_data_dir(None)
