from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AssetProjection, AssetSystemUserMap, SyncCheckpoint, SyncSnapshot, SystemUserProjection
from app.services.jumpserver.client import JumpServerClient, JumpServerClientError


def _upsert_asset(session: Session, jms_asset_id: str, hostname: str, ip: str) -> AssetProjection:
    existing = session.scalar(
        select(AssetProjection).where(AssetProjection.jms_asset_id == jms_asset_id)
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.hostname = hostname or existing.hostname
        existing.ip = ip or existing.ip
        existing.status = "active"
        existing.freshness_status = "fresh"
        existing.sync_at = now
        return existing

    asset = AssetProjection(
        jms_asset_id=jms_asset_id,
        hostname=hostname or "",
        ip=ip or "",
        status="active",
        freshness_status="fresh",
        sync_at=now,
    )
    session.add(asset)
    session.flush()
    return asset


def _upsert_system_user(session: Session, jms_system_user_id: str, name: str, username: str) -> SystemUserProjection:
    existing = session.scalar(
        select(SystemUserProjection).where(SystemUserProjection.jms_system_user_id == jms_system_user_id)
    )
    if existing:
        existing.name = name or existing.name
        existing.username = username or existing.username
        return existing

    user = SystemUserProjection(
        jms_system_user_id=jms_system_user_id,
        name=name or "",
        username=username or "",
    )
    session.add(user)
    session.flush()
    return user


def _upsert_asset_system_user_map(session: Session, asset_id: str, system_user_id: str) -> None:
    existing = session.scalar(
        select(AssetSystemUserMap).where(
            AssetSystemUserMap.asset_id == asset_id,
            AssetSystemUserMap.system_user_id == system_user_id,
        )
    )
    if existing:
        existing.relation_status = "active"
        return
    relation = AssetSystemUserMap(
        asset_id=asset_id,
        system_user_id=system_user_id,
        relation_status="active",
    )
    session.add(relation)
    session.flush()


def _upsert_checkpoint(session: Session, source: str, entity_type: str, cursor: str = "") -> None:
    cp = session.scalar(
        select(SyncCheckpoint).where(
            SyncCheckpoint.source == source,
            SyncCheckpoint.entity_type == entity_type,
        )
    )
    now = datetime.now(timezone.utc)
    if cp:
        cp.cursor = cursor
        cp.last_sync_at = now
        return
    session.add(
        SyncCheckpoint(
            source=source,
            entity_type=entity_type,
            cursor=cursor,
            last_sync_at=now,
        )
    )


def _parse_offset(cursor: str) -> int:
    if not cursor.startswith("offset:"):
        return 0
    raw = cursor.split(":", 1)[1].strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _current_offset(session: Session, source: str, entity_type: str) -> int:
    cp = session.scalar(
        select(SyncCheckpoint).where(
            SyncCheckpoint.source == source,
            SyncCheckpoint.entity_type == entity_type,
        )
    )
    if not cp:
        return 0
    return _parse_offset(cp.cursor)


def _parse_int_cursor(cursor: str, prefix: str) -> int:
    if not cursor.startswith(prefix):
        return 0
    raw = cursor.split(":", 1)[1].strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _current_int_checkpoint(session: Session, source: str, entity_type: str, prefix: str) -> int:
    cp = session.scalar(
        select(SyncCheckpoint).where(
            SyncCheckpoint.source == source,
            SyncCheckpoint.entity_type == entity_type,
        )
    )
    if not cp:
        return 0
    return _parse_int_cursor(cp.cursor, prefix=prefix)


def _parse_until_cursor(cursor: str) -> datetime | None:
    if not cursor.startswith("until:"):
        return None
    raw = cursor.split(":", 1)[1].strip()
    if not raw:
        return None
    return _parse_dt_maybe(raw)


def _format_until_cursor(value: datetime) -> str:
    return f"until:{value.astimezone(timezone.utc).isoformat()}"


def _current_until(session: Session, source: str, entity_type: str) -> datetime | None:
    cp = session.scalar(
        select(SyncCheckpoint).where(
            SyncCheckpoint.source == source,
            SyncCheckpoint.entity_type == entity_type,
        )
    )
    if not cp:
        return None
    return _parse_until_cursor(cp.cursor)


def _parse_updated_at_cursor(cursor: str) -> datetime | None:
    if not cursor.startswith("updated_at:"):
        return None
    raw = cursor.split(":", 1)[1].strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_updated_at_cursor(value: datetime) -> str:
    return f"updated_at:{value.astimezone(timezone.utc).isoformat()}"


def _current_updated_at(session: Session, source: str, entity_type: str) -> datetime | None:
    cp = session.scalar(
        select(SyncCheckpoint).where(
            SyncCheckpoint.source == source,
            SyncCheckpoint.entity_type == entity_type,
        )
    )
    if not cp:
        return None
    return _parse_updated_at_cursor(cp.cursor)


def _parse_dt_maybe(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _max_asset_updated_at(assets: list) -> datetime | None:
    max_value: datetime | None = None
    for asset in assets:
        parsed = _parse_dt_maybe(getattr(asset, "updated_at", ""))
        if not parsed:
            continue
        if max_value is None or parsed > max_value:
            max_value = parsed
    return max_value


def _fetch_all_upstream_asset_ids(client: JumpServerClient, page_size: int) -> set[str]:
    ids: set[str] = set()
    offset = 0
    while True:
        items, total = client.list_assets_page(limit=page_size, offset=offset)
        if not items:
            break
        for item in items:
            item_id = getattr(item, "id", "")
            if item_id:
                ids.add(item_id)
        offset += len(items)
        if len(items) < page_size:
            break
        if total is not None and offset >= total:
            break
    return ids


def _mark_missing_assets_inactive(session: Session, upstream_asset_ids: set[str]) -> tuple[int, bool, str]:
    stmt = select(AssetProjection).where(AssetProjection.status == "active")
    active_assets = list(session.scalars(stmt))
    missing_assets: list[AssetProjection] = []
    for asset in active_assets:
        if asset.jms_asset_id in upstream_asset_ids:
            continue
        missing_assets.append(asset)

    active_count = len(active_assets)
    missing_count = len(missing_assets)
    if active_count == 0 or missing_count == 0:
        return 0, False, ""

    ratio_limit = min(1.0, max(0.0, settings.sync_inactivation_guardrail_ratio))
    max_limit = max(1, settings.sync_inactivation_guardrail_max)
    missing_ratio = missing_count / active_count
    if missing_count > max_limit or missing_ratio > ratio_limit:
        reason = (
            f"inactivation guardrail blocked: missing={missing_count}, active={active_count}, "
            f"ratio={missing_ratio:.4f}, limit_ratio={ratio_limit:.4f}, limit_max={max_limit}"
        )
        return 0, True, reason

    changed = 0
    for asset in missing_assets:
        asset.status = "inactive"
        asset.freshness_status = "expired"
        changed += 1
    return changed, False, ""


def _refresh_asset_freshness(session: Session) -> dict[str, int]:
    now_utc = datetime.now(timezone.utc)
    fresh_cutoff = now_utc - timedelta(minutes=max(1, settings.sync_asset_fresh_minutes))
    stale_cutoff = now_utc - timedelta(hours=max(1, settings.sync_asset_stale_hours))
    now_local = datetime.now()
    fresh_cutoff_local = now_local - timedelta(minutes=max(1, settings.sync_asset_fresh_minutes))
    stale_cutoff_local = now_local - timedelta(hours=max(1, settings.sync_asset_stale_hours))

    counts = {"fresh": 0, "stale": 0, "expired": 0}
    assets = list(session.scalars(select(AssetProjection)))
    for asset in assets:
        sync_at = asset.sync_at
        if asset.status != "active":
            target = "expired"
        elif sync_at.tzinfo is None and sync_at >= fresh_cutoff_local:
            target = "fresh"
        elif sync_at.tzinfo is None and sync_at >= stale_cutoff_local:
            target = "stale"
        elif sync_at.tzinfo is not None and sync_at.astimezone(timezone.utc) >= fresh_cutoff:
            target = "fresh"
        elif sync_at.tzinfo is not None and sync_at.astimezone(timezone.utc) >= stale_cutoff:
            target = "stale"
        else:
            target = "expired"
        if asset.freshness_status != target:
            asset.freshness_status = target
        counts[target] += 1
    return counts


def _sanitize_strategy(value: str) -> str:
    lowered = (value or "").strip().lower()
    if lowered in {"auto", "timestamp", "full_compare"}:
        return lowered
    return "auto"


def _build_sync_checksum(
    *,
    source: str,
    offset: int,
    next_offset: int,
    strategy_used: str,
    watermark: str,
    fetched_assets: list[str],
    fetched_users: list[str],
    fetched_relations: list[str],
) -> str:
    payload = {
        "source": source,
        "offset": offset,
        "next_offset": next_offset,
        "strategy_used": strategy_used,
        "watermark": watermark,
        "assets": sorted(fetched_assets),
        "users": sorted(fetched_users),
        "relations": sorted(fetched_relations),
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_consistency_status(upstream_total_assets: int | None, local_total_assets: int | None) -> tuple[str, int | None, str]:
    if upstream_total_assets is None:
        return "unknown", None, "upstream total assets is unavailable"
    if local_total_assets is None:
        return "unknown", None, "local total assets is unavailable"

    delta = local_total_assets - upstream_total_assets
    if delta == 0:
        return "ok", 0, "local assets count is consistent with upstream total"

    if abs(delta) <= max(0, settings.sync_consistency_warn_delta_assets):
        return "warning", delta, "local assets count has small drift against upstream total"

    return "error", delta, "local assets count has significant drift against upstream total"


def _record_sync_snapshot(
    *,
    session: Session,
    source: str,
    offset: int,
    next_offset: int,
    page_size: int,
    fetched_assets: int,
    fetched_system_users: int,
    fetched_relations: int,
    upstream_total_assets: int | None,
    checksum: str,
    consistency_status: str,
    consistency_delta_assets: int | None,
    detail: str,
    local_total_assets: int | None = None,
    local_total_system_users: int | None = None,
    local_total_relations: int | None = None,
) -> SyncSnapshot:
    snapshot = SyncSnapshot(
        source=source,
        snapshot_type="sync_tick",
        offset=offset,
        next_offset=next_offset,
        page_size=page_size,
        fetched_assets=fetched_assets,
        fetched_system_users=fetched_system_users,
        fetched_relations=fetched_relations,
        upstream_total_assets=upstream_total_assets,
        local_total_assets=local_total_assets,
        local_total_system_users=local_total_system_users,
        local_total_relations=local_total_relations,
        consistency_status=consistency_status,
        consistency_delta_assets=consistency_delta_assets,
        checksum=checksum,
        detail=detail[:1024],
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def run_sync_once(session: Session, client: JumpServerClient, page_size: int = 50) -> dict[str, int | str | bool | None]:
    strategy_requested = _sanitize_strategy(settings.sync_incremental_strategy)
    strategy_used = "full_compare"
    strategy_fallback_reason = ""
    watermark_before: datetime | None = None
    watermark_after: datetime | None = None
    timestamp_ineffective_hit: bool | None = None
    timestamp_ineffective_hits: int | None = None
    force_full_until: datetime | None = None

    offset_entity_type = "asset"
    current_offset = 0
    assets = []
    total: int | None = None

    now_utc = datetime.now(timezone.utc)
    if strategy_requested == "auto":
        force_full_until = _current_until(
            session=session,
            source="jumpserver",
            entity_type="asset_ts_force_full_until",
        )

    should_try_timestamp = strategy_requested in {"auto", "timestamp"}
    if strategy_requested == "auto" and force_full_until and force_full_until > now_utc:
        should_try_timestamp = False
        strategy_fallback_reason = (
            f"timestamp incremental temporarily disabled until {force_full_until.isoformat()}"
        )

    if should_try_timestamp:
        offset_entity_type = "asset_ts_offset"
        current_offset = _current_offset(session, source="jumpserver", entity_type=offset_entity_type)
        watermark_before = _current_updated_at(
            session=session,
            source="jumpserver",
            entity_type="asset_ts_watermark",
        )
        if watermark_before is None:
            lookback = max(1, settings.sync_incremental_initial_lookback_hours)
            watermark_before = datetime.now(timezone.utc) - timedelta(hours=lookback)
        try:
            if not hasattr(client, "list_assets_updated_since_page"):
                raise JumpServerClientError("client does not implement incremental updated_at query")
            assets, total = client.list_assets_updated_since_page(
                updated_since=watermark_before.isoformat(),
                limit=page_size,
                offset=current_offset,
            )
            strategy_used = "timestamp"
        except JumpServerClientError as exc:
            strategy_fallback_reason = str(exc)[:512]
            offset_entity_type = "asset"
            current_offset = _current_offset(session, source="jumpserver", entity_type=offset_entity_type)
            assets, total = client.list_assets_page(limit=page_size, offset=current_offset)
            strategy_used = "full_compare"
    else:
        current_offset = _current_offset(session, source="jumpserver", entity_type=offset_entity_type)
        assets, total = client.list_assets_page(limit=page_size, offset=current_offset)

    asset_count = 0
    user_count = 0
    relation_count = 0
    fetched_asset_keys: list[str] = []
    fetched_user_keys: list[str] = []
    fetched_relation_keys: list[str] = []

    for asset in assets:
        if not asset.id:
            continue
        fetched_asset_keys.append(asset.id)
        asset_row = _upsert_asset(
            session=session,
            jms_asset_id=asset.id,
            hostname=asset.hostname,
            ip=asset.ip or asset.address,
        )
        asset_count += 1

        users = client.list_asset_system_users(asset.id)
        for user in users:
            if not user.id:
                continue
            fetched_user_keys.append(user.id)
            fetched_relation_keys.append(f"{asset.id}:{user.id}")
            user_row = _upsert_system_user(
                session=session,
                jms_system_user_id=user.id,
                name=user.name,
                username=user.username,
            )
            user_count += 1
            _upsert_asset_system_user_map(
                session=session,
                asset_id=asset_row.id,
                system_user_id=user_row.id,
            )
            relation_count += 1

    if not assets:
        next_offset = 0
    else:
        guessed_next = current_offset + len(assets)
        if total is not None and guessed_next >= total:
            next_offset = 0
        elif len(assets) < page_size:
            next_offset = 0
        else:
            next_offset = guessed_next

    checkpoint_cursor = f"offset:{next_offset}"
    _upsert_checkpoint(session, source="jumpserver", entity_type=offset_entity_type, cursor=checkpoint_cursor)
    if strategy_used == "full_compare":
        _upsert_checkpoint(session, source="jumpserver", entity_type="system_user", cursor=checkpoint_cursor)

    if strategy_used == "timestamp":
        cycle_completed = next_offset == 0
    else:
        cycle_completed = next_offset == 0 and (current_offset > 0 or bool(assets) or total == 0)

    inactivated_assets = 0
    inactivation_guardrail_blocked = False
    inactivation_guardrail_reason = ""
    if strategy_used == "timestamp" and cycle_completed:
        max_updated = _max_asset_updated_at(assets)
        timestamp_ineffective_hit = bool(assets) and max_updated is None
        previous_hits = _current_int_checkpoint(
            session=session,
            source="jumpserver",
            entity_type="asset_ts_ineffective_hits",
            prefix="hits:",
        )
        timestamp_ineffective_hits = previous_hits + 1 if timestamp_ineffective_hit else 0
        _upsert_checkpoint(
            session=session,
            source="jumpserver",
            entity_type="asset_ts_ineffective_hits",
            cursor=f"hits:{timestamp_ineffective_hits}",
        )
        if strategy_requested == "auto" and timestamp_ineffective_hits >= max(1, settings.sync_timestamp_ineffective_threshold):
            force_full_until = now_utc + timedelta(minutes=max(1, settings.sync_timestamp_force_full_minutes))
            _upsert_checkpoint(
                session=session,
                source="jumpserver",
                entity_type="asset_ts_force_full_until",
                cursor=_format_until_cursor(force_full_until),
            )
            strategy_fallback_reason = (
                f"timestamp incremental appears ineffective; enforce full_compare until {force_full_until.isoformat()}"
            )[:512]
        if max_updated is not None:
            watermark_after = max_updated
        elif assets:
            watermark_after = datetime.now(timezone.utc)
        else:
            watermark_after = watermark_before
        if watermark_after is not None:
            _upsert_checkpoint(
                session=session,
                source="jumpserver",
                entity_type="asset_ts_watermark",
                cursor=_format_updated_at_cursor(watermark_after),
            )
    elif strategy_used == "full_compare" and cycle_completed:
        upstream_asset_ids = _fetch_all_upstream_asset_ids(client=client, page_size=page_size)
        (
            inactivated_assets,
            inactivation_guardrail_blocked,
            inactivation_guardrail_reason,
        ) = _mark_missing_assets_inactive(session=session, upstream_asset_ids=upstream_asset_ids)

    freshness_counts = _refresh_asset_freshness(session=session)

    checksum_watermark = watermark_after or watermark_before
    checksum = _build_sync_checksum(
        source="jumpserver",
        offset=current_offset,
        next_offset=next_offset,
        strategy_used=strategy_used,
        watermark=checksum_watermark.isoformat() if checksum_watermark else "",
        fetched_assets=fetched_asset_keys,
        fetched_users=fetched_user_keys,
        fetched_relations=fetched_relation_keys,
    )

    local_total_assets: int | None = None
    local_total_system_users: int | None = None
    local_total_relations: int | None = None
    consistency_status = "skipped"
    consistency_delta_assets: int | None = None
    consistency_detail = "consistency check skipped because sync cycle is not completed"
    if strategy_used == "timestamp":
        consistency_detail = "consistency check skipped for timestamp incremental strategy"
        if timestamp_ineffective_hit:
            consistency_detail = (
                f"{consistency_detail}; upstream assets missing updated_at field"
            )
        if force_full_until and strategy_fallback_reason:
            consistency_detail = f"{consistency_detail}; {strategy_fallback_reason}"
    elif cycle_completed:
        now_utc = datetime.now(timezone.utc)

        def _count_local_totals(cutoff: datetime) -> tuple[int, int, int]:
            fresh_asset_ids_subquery = (
                select(AssetProjection.id)
                .where(
                    AssetProjection.status == "active",
                    AssetProjection.sync_at >= cutoff,
                )
            )

            counted_assets = int(
                session.scalar(
                    select(func.count())
                    .select_from(AssetProjection)
                    .where(
                        AssetProjection.status == "active",
                        AssetProjection.sync_at >= cutoff,
                    )
                )
                or 0
            )
            counted_users = int(
                session.scalar(
                    select(func.count(func.distinct(SystemUserProjection.id)))
                    .select_from(SystemUserProjection)
                    .join(AssetSystemUserMap, AssetSystemUserMap.system_user_id == SystemUserProjection.id)
                    .where(
                        AssetSystemUserMap.relation_status == "active",
                        AssetSystemUserMap.asset_id.in_(fresh_asset_ids_subquery),
                    )
                )
                or 0
            )
            counted_relations = int(
                session.scalar(
                    select(func.count())
                    .select_from(AssetSystemUserMap)
                    .where(
                        AssetSystemUserMap.relation_status == "active",
                        AssetSystemUserMap.asset_id.in_(fresh_asset_ids_subquery),
                    )
                )
                or 0
            )
            return counted_assets, counted_users, counted_relations

        base_cutoff = now_utc - timedelta(hours=max(1, settings.sync_consistency_freshness_hours))
        local_total_assets, local_total_system_users, local_total_relations = _count_local_totals(base_cutoff)

        if total is not None and total > 0 and local_total_assets > total * 5:
            short_cutoff = now_utc - timedelta(minutes=10)
            short_assets, short_users, short_relations = _count_local_totals(short_cutoff)
            if abs(short_assets - total) < abs(local_total_assets - total):
                local_total_assets = short_assets
                local_total_system_users = short_users
                local_total_relations = short_relations

        consistency_status, consistency_delta_assets, consistency_detail = _build_consistency_status(
            upstream_total_assets=total,
            local_total_assets=local_total_assets,
        )
        if inactivated_assets > 0:
            consistency_detail = f"{consistency_detail}; inactivated_assets={inactivated_assets}"
        if inactivation_guardrail_blocked:
            consistency_detail = f"{consistency_detail}; {inactivation_guardrail_reason}"

    snapshot = _record_sync_snapshot(
        session=session,
        source="jumpserver",
        offset=current_offset,
        next_offset=next_offset,
        page_size=page_size,
        fetched_assets=asset_count,
        fetched_system_users=user_count,
        fetched_relations=relation_count,
        upstream_total_assets=total,
        checksum=checksum,
        consistency_status=consistency_status,
        consistency_delta_assets=consistency_delta_assets,
        detail=consistency_detail,
        local_total_assets=local_total_assets,
        local_total_system_users=local_total_system_users,
        local_total_relations=local_total_relations,
    )
    session.flush()

    return {
        "assets": asset_count,
        "system_users": user_count,
        "relations": relation_count,
        "offset": current_offset,
        "next_offset": next_offset,
        "strategy_requested": strategy_requested,
        "strategy_used": strategy_used,
        "strategy_fallback_reason": strategy_fallback_reason or None,
        "watermark_before": watermark_before.isoformat() if watermark_before else None,
        "watermark_after": watermark_after.isoformat() if watermark_after else None,
        "timestamp_ineffective_hit": timestamp_ineffective_hit,
        "timestamp_ineffective_hits": timestamp_ineffective_hits,
        "force_full_until": force_full_until.isoformat() if force_full_until else None,
        "cycle_completed": cycle_completed,
        "consistency_status": consistency_status,
        "consistency_delta_assets": consistency_delta_assets,
        "inactivated_assets": inactivated_assets,
        "inactivation_guardrail_blocked": inactivation_guardrail_blocked,
        "inactivation_guardrail_reason": inactivation_guardrail_reason or None,
        "fresh_assets": freshness_counts["fresh"],
        "stale_assets": freshness_counts["stale"],
        "expired_assets": freshness_counts["expired"],
        "snapshot_id": snapshot.id,
    }


def refresh_asset_once(
    session: Session,
    client: JumpServerClient,
    jms_asset_id: str,
    search_limit: int = 20,
) -> dict[str, int | str | bool | None]:
    asset_key = (jms_asset_id or "").strip()
    if not asset_key:
        raise ValueError("jms_asset_id is required")

    page_limit = max(1, search_limit)
    candidate_assets, _ = client.list_assets_page(search=asset_key, limit=page_limit, offset=0)
    matched_asset = next((item for item in candidate_assets if item.id == asset_key), None)
    scan_pages = max(1, settings.execution_gate_refresh_scan_pages)
    scanned_pages = 0
    if not matched_asset:
        # Some JumpServer deployments do not support searching by UUID, so fallback to bounded page scan.
        offset = 0
        for _ in range(scan_pages):
            scanned_pages += 1
            page_assets, total = client.list_assets_page(limit=page_limit, offset=offset)
            matched_asset = next((item for item in page_assets if item.id == asset_key), None)
            if matched_asset:
                break
            if not page_assets:
                break
            offset += len(page_assets)
            if total is not None and offset >= total:
                break
    if not matched_asset:
        return {
            "found": False,
            "jms_asset_id": asset_key,
            "users": 0,
            "relations_active": 0,
            "relations_inactivated": 0,
            "scan_pages": scanned_pages,
        }

    asset_row = _upsert_asset(
        session=session,
        jms_asset_id=matched_asset.id,
        hostname=matched_asset.hostname,
        ip=matched_asset.ip or matched_asset.address,
    )

    users = client.list_asset_system_users(asset_key)
    active_system_user_row_ids: set[str] = set()
    upserted_users = 0
    for user in users:
        if not user.id:
            continue
        user_row = _upsert_system_user(
            session=session,
            jms_system_user_id=user.id,
            name=user.name,
            username=user.username,
        )
        upserted_users += 1
        active_system_user_row_ids.add(user_row.id)
        _upsert_asset_system_user_map(
            session=session,
            asset_id=asset_row.id,
            system_user_id=user_row.id,
        )

    inactivated_relations = 0
    existing_relations = list(
        session.scalars(select(AssetSystemUserMap).where(AssetSystemUserMap.asset_id == asset_row.id))
    )
    for relation in existing_relations:
        if relation.system_user_id in active_system_user_row_ids:
            if relation.relation_status != "active":
                relation.relation_status = "active"
            continue
        if relation.relation_status != "inactive":
            relation.relation_status = "inactive"
            inactivated_relations += 1

    freshness_counts = _refresh_asset_freshness(session=session)
    session.flush()

    return {
        "found": True,
        "asset_id": asset_row.id,
        "jms_asset_id": asset_key,
        "users": upserted_users,
        "relations_active": len(active_system_user_row_ids),
        "relations_inactivated": inactivated_relations,
        "scan_pages": scanned_pages,
        "fresh_assets": freshness_counts["fresh"],
        "stale_assets": freshness_counts["stale"],
        "expired_assets": freshness_counts["expired"],
    }
