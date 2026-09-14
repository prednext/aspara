"""Unit tests for aspara.tenancy (tenant id parsing and LibsqlTenant specs)."""

from __future__ import annotations

import pytest

from aspara.tenancy import (
    DEFAULT_TENANT,
    LibsqlTenant,
    tenant_id_from_request,
)


def test_libsql_tenant_requires_base_dir_or_database() -> None:
    with pytest.raises(ValueError, match="base_dir"):
        LibsqlTenant()
    with pytest.raises(ValueError, match="base_dir"):
        LibsqlTenant(base_dir="  ", database="")
    assert LibsqlTenant(base_dir="/tmp/t").base_dir == "/tmp/t"
    assert LibsqlTenant(database="libsql://example").database == "libsql://example"


def test_tenant_id_precedence_header_then_query_then_cookie() -> None:
    assert tenant_id_from_request({}) == DEFAULT_TENANT
    assert tenant_id_from_request({}, query={"tenant": "q"}, cookies={"aspara_tenant": "c"}) == "q"
    assert tenant_id_from_request({"X-Aspara-Tenant": "h"}, query={"tenant": "q"}) == "h"
    assert tenant_id_from_request({}, cookies={"aspara_tenant": "c"}) == "c"
    assert tenant_id_from_request({}, query={"tenant": "../etc"}) == DEFAULT_TENANT
