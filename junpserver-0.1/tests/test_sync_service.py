from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models import AssetProjection, AssetSystemUserMap, SyncCheckpoint, SyncSnapshot, SystemUserProjection
from app.services.sync_service import refresh_asset_once, run_sync_once


class FakeSyncClient:
    def __init__(self):
        self.calls = []

    def list_assets(self, search=None, limit=50, offset=0):
        # Kept for compatibility if older code path calls this method.
        assets, _ = self.list_assets_page(search=search, limit=limit, offset=offset)
        return assets

    def list_assets_page(self, search=None, limit=50, offset=0):
        self.calls.append(offset)

        class Asset:
            def __init__(self, asset_id: str, hostname: str, ip: str):
                self.id = asset_id
                self.hostname = hostname
                self.ip = ip
                self.address = ""

        if offset == 0:
            return [Asset("asset-1", "web-01", "10.0.0.11")], 2
        if offset == 1:
            return [Asset("asset-2", "web-02", "10.0.0.12")], 2
        return [], 2

    def list_asset_system_users(self, asset_id: str):
        class User:
            id = "su-1"
            name = "root"
            username = "root"

        assert asset_id in ("asset-1", "asset-2", "asset-ts-1", "asset-nu-1")
        return [User()]


class FakeTimestampSyncClient(FakeSyncClient):
    def __init__(self):
        super().__init__()
        self.incremental_calls = []

    def list_assets_updated_since_page(self, updated_since: str, limit: int = 50, offset: int = 0):
        self.incremental_calls.append((updated_since, offset))

        class Asset:
            def __init__(self, asset_id: str, hostname: str, ip: str, updated_at: str):
                self.id = asset_id
                self.hostname = hostname
                self.ip = ip
                self.address = ""
                self.updated_at = updated_at

        return (
            [
                Asset(
                    "asset-ts-1",
                    "ts-01",
                    "10.0.1.11",
                    "2026-04-02T12:30:00+00:00",
                )
            ],
            1,
        )


class FakeTimestampNoUpdatedClient(FakeSyncClient):
    def __init__(self):
        super().__init__()
        self.incremental_calls = 0
        self.full_calls = 0

    def list_assets_updated_since_page(self, updated_since: str, limit: int = 50, offset: int = 0):
        self.incremental_calls += 1

        class Asset:
            def __init__(self, asset_id: str):
                self.id = asset_id
                self.hostname = "nu-01"
                self.ip = "10.0.2.11"
                self.address = ""

        return [Asset("asset-nu-1")], 1

    def list_assets_page(self, search=None, limit=50, offset=0, extra_params=None):
        self.full_calls += 1
        return super().list_assets_page(search=search, limit=limit, offset=offset)


class FakeSingleAssetRefreshClient:
    def list_assets_page(self, search=None, limit=50, offset=0, extra_params=None):
        class Asset:
            def __init__(self, asset_id: str, hostname: str, ip: str):
                self.id = asset_id
                self.hostname = hostname
                self.ip = ip
                self.address = ""

        if offset != 0:
            return [], 1
        if search == "asset-refresh-1":
            return [Asset("asset-refresh-1", "refresh-host", "10.8.8.8")], 1
        return [], 0

    def list_asset_system_users(self, asset_id: str):
        class User:
            def __init__(self, user_id: str, name: str, username: str):
                self.id = user_id
                self.name = name
                self.username = username

        if asset_id != "asset-refresh-1":
            return []
        return [
            User("su-refresh-1", "root", "root"),
            User("su-refresh-2", "ops", "ops"),
        ]


class FakeSingleAssetRefreshFallbackClient:
    def list_assets_page(self, search=None, limit=50, offset=0, extra_params=None):
        class Asset:
            def __init__(self, asset_id: str, hostname: str, ip: str):
                self.id = asset_id
                self.hostname = hostname
                self.ip = ip
                self.address = ""

        if search is not None:
            return [], 0
        if offset == 0:
            return [Asset("asset-x-1", "x1", "10.1.1.1"), Asset("asset-fallback-1", "fallback-host", "10.1.1.2")], 2
        return [], 2

    def list_asset_system_users(self, asset_id: str):
        class User:
            id = "su-fallback-1"
            name = "root"
            username = "root"

        return [User()]


def test_run_sync_once_creates_projection_data(db_session):
    result = run_sync_once(session=db_session, client=FakeSyncClient(), page_size=10)

    assert result["assets"] == 1
    assert result["system_users"] == 1
    assert result["relations"] == 1

    asset = db_session.query(AssetProjection).one()
    user = db_session.query(SystemUserProjection).one()
    relation = db_session.query(AssetSystemUserMap).one()
    checkpoints = db_session.query(SyncCheckpoint).all()
    snapshots = db_session.query(SyncSnapshot).all()

    assert asset.jms_asset_id == "asset-1"
    assert user.jms_system_user_id == "su-1"
    assert relation.asset_id == asset.id
    assert relation.system_user_id == user.id
    assert len(checkpoints) == 2
    assert len(snapshots) == 1
    assert result["snapshot_id"] == snapshots[0].id
    assert result["consistency_status"] in ("warning", "ok", "error", "unknown")


def test_run_sync_once_advances_and_resets_offset(db_session):
    fake = FakeSyncClient()

    first = run_sync_once(session=db_session, client=fake, page_size=1)
    db_session.commit()
    second = run_sync_once(session=db_session, client=fake, page_size=1)
    db_session.commit()
    third = run_sync_once(session=db_session, client=fake, page_size=1)
    db_session.commit()

    assert first["offset"] == 0
    assert first["next_offset"] == 1
    assert second["offset"] == 1
    assert second["next_offset"] == 0
    assert third["offset"] == 0
    assert third["next_offset"] == 1
    assert fake.calls[:3] == [0, 1, 0]
    assert first["cycle_completed"] is False
    assert second["cycle_completed"] is True
    assert second["consistency_status"] == "ok"
    snapshots = db_session.query(SyncSnapshot).all()
    assert len(snapshots) == 3


def test_run_sync_once_timestamp_strategy_updates_watermark(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sync_incremental_strategy", "timestamp")
    monkeypatch.setattr(settings, "sync_incremental_initial_lookback_hours", 24)
    fake = FakeTimestampSyncClient()

    result = run_sync_once(session=db_session, client=fake, page_size=10)
    db_session.commit()

    assert result["strategy_requested"] == "timestamp"
    assert result["strategy_used"] == "timestamp"
    assert result["strategy_fallback_reason"] is None
    assert result["cycle_completed"] is True
    assert result["consistency_status"] == "skipped"
    assert result["watermark_before"] is not None
    assert result["watermark_after"] == "2026-04-02T12:30:00+00:00"
    assert len(fake.incremental_calls) == 1

    ts_offset_cp = db_session.query(SyncCheckpoint).filter(SyncCheckpoint.entity_type == "asset_ts_offset").one()
    ts_watermark_cp = db_session.query(SyncCheckpoint).filter(SyncCheckpoint.entity_type == "asset_ts_watermark").one()
    assert ts_offset_cp.cursor == "offset:0"
    assert ts_watermark_cp.cursor.startswith("updated_at:2026-04-02T12:30:00+00:00")


def test_run_sync_once_auto_fallbacks_to_full_compare_when_incremental_unsupported(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sync_incremental_strategy", "auto")
    fake = FakeSyncClient()

    result = run_sync_once(session=db_session, client=fake, page_size=10)
    db_session.commit()

    assert result["strategy_requested"] == "auto"
    assert result["strategy_used"] == "full_compare"
    assert "incremental" in (result["strategy_fallback_reason"] or "")
    assert result["assets"] == 1


def test_run_sync_once_auto_forces_full_compare_when_timestamp_ineffective(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sync_incremental_strategy", "auto")
    monkeypatch.setattr(settings, "sync_timestamp_ineffective_threshold", 2)
    monkeypatch.setattr(settings, "sync_timestamp_force_full_minutes", 30)
    fake = FakeTimestampNoUpdatedClient()

    first = run_sync_once(session=db_session, client=fake, page_size=10)
    db_session.commit()
    second = run_sync_once(session=db_session, client=fake, page_size=10)
    db_session.commit()
    third = run_sync_once(session=db_session, client=fake, page_size=10)
    db_session.commit()

    assert first["strategy_used"] == "timestamp"
    assert first["timestamp_ineffective_hit"] is True
    assert first["timestamp_ineffective_hits"] == 1

    assert second["strategy_used"] == "timestamp"
    assert second["timestamp_ineffective_hits"] == 2
    assert second["force_full_until"] is not None
    assert "ineffective" in (second["strategy_fallback_reason"] or "")

    assert third["strategy_used"] == "full_compare"
    assert "temporarily disabled" in (third["strategy_fallback_reason"] or "")
    assert fake.incremental_calls == 2
    assert fake.full_calls >= 1


def test_run_sync_once_full_compare_marks_missing_assets_inactive(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sync_incremental_strategy", "full_compare")
    monkeypatch.setattr(settings, "sync_inactivation_guardrail_ratio", 1.0)
    monkeypatch.setattr(settings, "sync_inactivation_guardrail_max", 10000)
    seed_asset = AssetProjection(
        jms_asset_id="asset-missing-1",
        hostname="legacy",
        ip="10.10.10.10",
        status="active",
        freshness_status="fresh",
        sync_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.add(seed_asset)
    db_session.commit()

    fake = FakeSyncClient()
    result = run_sync_once(session=db_session, client=fake, page_size=10)
    db_session.commit()

    missing = db_session.query(AssetProjection).filter(AssetProjection.jms_asset_id == "asset-missing-1").one()
    assert result["strategy_used"] == "full_compare"
    assert result["inactivated_assets"] >= 1
    assert result["inactivation_guardrail_blocked"] is False
    assert missing.status == "inactive"
    assert missing.freshness_status == "expired"


def test_run_sync_once_full_compare_inactivation_guardrail_blocks_mass_changes(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sync_incremental_strategy", "full_compare")
    monkeypatch.setattr(settings, "sync_inactivation_guardrail_ratio", 0.2)
    monkeypatch.setattr(settings, "sync_inactivation_guardrail_max", 1)

    seed_assets = [
        AssetProjection(
            jms_asset_id=f"asset-guardrail-{idx}",
            hostname=f"legacy-{idx}",
            ip=f"10.9.0.{idx}",
            status="active",
            freshness_status="fresh",
            sync_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        for idx in range(1, 6)
    ]
    db_session.add_all(seed_assets)
    db_session.commit()

    fake = FakeSyncClient()
    result = run_sync_once(session=db_session, client=fake, page_size=10)
    db_session.commit()

    assert result["inactivated_assets"] == 0
    assert result["inactivation_guardrail_blocked"] is True
    assert "guardrail blocked" in (result["inactivation_guardrail_reason"] or "")

    still_active = (
        db_session.query(AssetProjection)
        .filter(AssetProjection.jms_asset_id.like("asset-guardrail-%"), AssetProjection.status == "active")
        .count()
    )
    assert still_active == 5


def test_run_sync_once_refreshes_freshness_status_for_active_assets(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sync_incremental_strategy", "timestamp")
    monkeypatch.setattr(settings, "sync_asset_fresh_minutes", 10)
    monkeypatch.setattr(settings, "sync_asset_stale_hours", 3)

    stale_asset = AssetProjection(
        jms_asset_id="asset-stale-1",
        hostname="stale-host",
        ip="10.0.9.1",
        status="active",
        freshness_status="fresh",
        sync_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db_session.add(stale_asset)
    db_session.commit()

    class EmptyTimestampClient:
        def list_assets_updated_since_page(self, updated_since: str, limit: int = 50, offset: int = 0):
            return [], 0

        def list_asset_system_users(self, asset_id: str):
            return []

    result = run_sync_once(session=db_session, client=EmptyTimestampClient(), page_size=10)
    db_session.commit()

    refreshed = db_session.query(AssetProjection).filter(AssetProjection.jms_asset_id == "asset-stale-1").one()
    assert result["strategy_used"] == "timestamp"
    assert refreshed.status == "active"
    assert refreshed.freshness_status == "stale"


def test_refresh_asset_once_updates_asset_and_deactivates_removed_relations(db_session):
    existing_asset = AssetProjection(
        jms_asset_id="asset-refresh-1",
        hostname="legacy-host",
        ip="10.0.0.9",
        status="inactive",
        freshness_status="expired",
        sync_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db_session.add(existing_asset)
    db_session.flush()

    old_user = SystemUserProjection(jms_system_user_id="su-old", name="old", username="old")
    db_session.add(old_user)
    db_session.flush()
    db_session.add(
        AssetSystemUserMap(
            asset_id=existing_asset.id,
            system_user_id=old_user.id,
            relation_status="active",
        )
    )
    db_session.commit()

    result = refresh_asset_once(
        session=db_session,
        client=FakeSingleAssetRefreshClient(),
        jms_asset_id="asset-refresh-1",
    )
    db_session.commit()

    assert result["found"] is True
    assert result["users"] == 2
    assert result["relations_active"] == 2
    assert result["relations_inactivated"] == 1

    refreshed_asset = db_session.query(AssetProjection).filter(AssetProjection.jms_asset_id == "asset-refresh-1").one()
    assert refreshed_asset.status == "active"
    assert refreshed_asset.freshness_status == "fresh"
    assert refreshed_asset.hostname == "refresh-host"
    assert refreshed_asset.ip == "10.8.8.8"

    active_relations = (
        db_session.query(AssetSystemUserMap)
        .filter(
            AssetSystemUserMap.asset_id == refreshed_asset.id,
            AssetSystemUserMap.relation_status == "active",
        )
        .count()
    )
    inactive_relations = (
        db_session.query(AssetSystemUserMap)
        .filter(
            AssetSystemUserMap.asset_id == refreshed_asset.id,
            AssetSystemUserMap.relation_status == "inactive",
        )
        .count()
    )
    assert active_relations == 2
    assert inactive_relations == 1


def test_refresh_asset_once_returns_not_found_when_upstream_missing(db_session):
    result = refresh_asset_once(
        session=db_session,
        client=FakeSingleAssetRefreshClient(),
        jms_asset_id="asset-does-not-exist",
    )
    assert result["found"] is False
    assert result["jms_asset_id"] == "asset-does-not-exist"


def test_refresh_asset_once_fallback_scans_pages_when_search_misses(db_session, monkeypatch):
    monkeypatch.setattr(settings, "execution_gate_refresh_scan_pages", 5)
    result = refresh_asset_once(
        session=db_session,
        client=FakeSingleAssetRefreshFallbackClient(),
        jms_asset_id="asset-fallback-1",
    )
    assert result["found"] is True
    assert result["jms_asset_id"] == "asset-fallback-1"
    assert result["scan_pages"] >= 1
