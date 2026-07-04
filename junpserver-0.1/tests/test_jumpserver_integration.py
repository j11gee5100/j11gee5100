from __future__ import annotations

import os

import pytest

from app.services.jumpserver.client import JumpServerClient


def _integration_enabled() -> bool:
    return os.getenv("RUN_JUMPSERVER_INTEGRATION", "false").lower() == "true"


@pytest.mark.integration
def test_jumpserver_assets_integration():
    if not _integration_enabled():
        pytest.skip("set RUN_JUMPSERVER_INTEGRATION=true to run real JumpServer tests")

    base_url = os.getenv("JUMPSERVER_BASE_URL", "").strip()
    token = os.getenv("JUMPSERVER_TOKEN", "").strip()
    if not base_url or not token:
        pytest.skip("missing JUMPSERVER_BASE_URL or JUMPSERVER_TOKEN")

    client = JumpServerClient(base_url=base_url, token=token)
    assets = client.list_assets(limit=5, offset=0)
    assert isinstance(assets, list)

