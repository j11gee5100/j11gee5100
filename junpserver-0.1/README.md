# OpsPaw Bootstrap Skeleton

This repository now contains the initial runnable skeleton for OpsPaw.

## What is included

- FastAPI API service (`app/api/main.py`)
- Worker entry points:
  - `app/workers/orchestrator.py`
  - `app/workers/sync.py`
  - `app/workers/callback.py`
  - `app/workers/scheduler.py`
- Linux deployment baseline:
  - `docker-compose.yml`
  - `Dockerfile`
  - `docker/nginx/nginx.conf`
  - `docker/systemd/opspaw-compose.service`

## Quick start (Linux server)

1. Copy environment template.

```bash
cp .env.example .env
```

2. Start stack.

```bash
docker compose up -d --build
```

3. Verify API.

```bash
curl http://127.0.0.1/healthz
curl http://127.0.0.1/api/v1/system/info
curl http://127.0.0.1/api/v1/integrations/jumpserver/check
```

## Database bootstrap and migration

Initialize schema quickly:

```bash
python scripts/init_db.py
```

Run Alembic migration:

```bash
alembic upgrade head
```

## JumpServer interface probe

1. Fill JumpServer values in `.env`.

```bash
JUMPSERVER_BASE_URL=http://your-jumpserver
JUMPSERVER_TOKEN=your_token
JUMPSERVER_EXECUTION_TIMEOUT_SEC=600
JUMPSERVER_INCREMENTAL_UPDATED_AT_PARAM=updated_at__gte
SYNC_INCREMENTAL_STRATEGY=auto
SYNC_INCREMENTAL_INITIAL_LOOKBACK_HOURS=24
SYNC_TIMESTAMP_INEFFECTIVE_THRESHOLD=3
SYNC_TIMESTAMP_FORCE_FULL_MINUTES=30
SYNC_ASSET_FRESH_MINUTES=30
SYNC_ASSET_STALE_HOURS=6
SYNC_INACTIVATION_GUARDRAIL_RATIO=0.2
SYNC_INACTIVATION_GUARDRAIL_MAX=500
EXECUTION_GATE_AUTO_REFRESH_ENABLED=false
EXECUTION_GATE_REFRESH_SEARCH_LIMIT=20
EXECUTION_GATE_REFRESH_SCAN_PAGES=5
TASK_REFRESH_RETRY_MAX_HOURS=24
TASK_REFRESH_RETRY_SAME_ASSET_MAX_RETRIES=2
TASK_REFRESH_RETRY_TASK_COOLDOWN_MINUTES=30
TASK_REFRESH_RETRY_WINDOW_SIZE=5
TASK_REFRESH_RETRY_MAX_WINDOWS_PER_REQUEST=2
TASK_REFRESH_RETRY_SCHEDULER_ENABLED=false
TASK_REFRESH_RETRY_SCHEDULER_INTERVAL_SEC=300
TASK_REFRESH_RETRY_SCHEDULER_HOURS=24
TASK_REFRESH_RETRY_SCHEDULER_SOURCE=
TASK_REFRESH_RETRY_SCHEDULER_FAILURE_CODES=ASSET_STALE,ASSET_EXPIRED
TASK_REFRESH_RETRY_SCHEDULER_LIMIT=100
TASK_REFRESH_RETRY_SCHEDULER_WINDOW_SIZE=5
TASK_REFRESH_RETRY_SCHEDULER_MAX_WINDOWS=1
APPROVAL_TIMEOUT_HOURS=24
APPROVAL_EXPIRE_CHECK_INTERVAL_SEC=60
APPROVAL_EXPIRE_BATCH_SIZE=200
APPROVAL_ESCALATION_ENABLED=false
APPROVAL_ESCALATION_AFTER_MINUTES=30
APPROVAL_MAX_LEVELS=2
POLICY_BUILTIN_BLACKLIST=rm -rf /,mkfs,shutdown -h,reboot,poweroff,:(){:|:&};:
METRICS_PREAGGREGATION_SCHEDULER_ENABLED=true
METRICS_PREAGGREGATION_INTERVAL_SEC=300
METRICS_PREAGGREGATION_HOURLY_LOOKBACK_HOURS=72
METRICS_PREAGGREGATION_DAILY_LOOKBACK_DAYS=30
METRICS_PREAGGREGATION_MAX_LAG_MINUTES=30
```

2. Run probe script.

```bash
python scripts/probe_jumpserver.py
python scripts/probe_jumpserver.py --pending-diagnosis
```

The script currently checks:

- auto-detected API mode (`legacy_v3` / `v4`)
- assets:
  - `GET /api/v1/perms/users/assets/` (legacy)
  - `GET /api/v1/perms/users/my/assets/` or `/api/v1/assets/assets/` (v4)
- system users:
  - `GET /api/v1/perms/users/assets/{asset_id}/system-users/` (legacy)
  - `GET /api/v1/accounts/accounts/?asset_id=...` (v4)
- `GET /api/v1/audits/command-executions-hosts-relations/`
- Optional pending diagnosis:
  - `GET /api/v1/health/`
  - legacy v3: `GET /api/v1/ops/command-executions/` + celery probes
  - v4: `GET /api/v1/ops/job-executions/` + `task-detail` probes
  - v4 output now includes `v4_root_cause_hints` (`status_counts`, `reason_counts`, `likely_root_cause`)

Manual one-shot debug endpoints (for development only):

```bash
curl -X POST http://127.0.0.1/api/v1/admin/sync/once
curl -X POST http://127.0.0.1/api/v1/admin/sync/assets/{jms_asset_id}/refresh
curl -X POST http://127.0.0.1/api/v1/admin/orchestrator/tick
```

These endpoints are disabled by default (`APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=false`).
Enable only for local debugging and turn off in production.

Execution query endpoints:

```bash
curl -X POST http://127.0.0.1/api/v1/tasks -H "Content-Type: application/json" -d '{"command":"hostname","target_asset_id":"asset-id","run_as_system_user_id":"system-user-id","callback_url":"https://example.com/callback","callback_secret":"secret"}'
curl -X POST http://127.0.0.1/api/v1/tasks/{task_id}/cancel -H "Content-Type: application/json" -d '{"reason":"manual cancel"}'
curl "http://127.0.0.1/api/v1/tasks/{task_id}/approval"
curl "http://127.0.0.1/api/v1/approvals?status=pending&source=api&risk_level=high-risk"
curl "http://127.0.0.1/api/v1/approvals/pending"
curl -X POST http://127.0.0.1/api/v1/approvals/{approval_id}/approve -H "Content-Type: application/json" -H "X-Operator-Id: alice" -d '{"reason":"approved"}'
curl -X POST http://127.0.0.1/api/v1/approvals/{approval_id}/reject -H "Content-Type: application/json" -H "X-Operator-Id: alice" -d '{"reason":"unsafe in current window"}'
curl -X POST http://127.0.0.1/api/v1/approvals/{approval_id}/escalate -H "Content-Type: application/json" -H "X-Operator-Id: alice" -d '{"reason":"need L2 approval"}'
curl "http://127.0.0.1/api/v1/templates/commands?enabled=true&limit=20"
curl -X POST http://127.0.0.1/api/v1/templates/commands -H "Content-Type: application/json" -H "X-Operator-Id: alice" -d '{"template_id":"tpl_disk_check","name":"Disk Check","command":"df -h","risk_level":"readonly"}'
curl -X PATCH http://127.0.0.1/api/v1/templates/commands/tpl_disk_check -H "Content-Type: application/json" -H "X-Operator-Id: alice" -d '{"enabled":false}'
curl "http://127.0.0.1/api/v1/policies/command-blacklist?enabled=true&limit=50"
curl -X POST http://127.0.0.1/api/v1/policies/command-blacklist -H "Content-Type: application/json" -H "X-Operator-Id: alice" -d '{"pattern":"danger-cmd","hard_block":true}'
curl -X POST http://127.0.0.1/api/v1/policies/evaluate -H "Content-Type: application/json" -d '{"command":"hostname","requested_risk_level":"readonly"}'
curl "http://127.0.0.1/api/v1/governance/audits?entity_type=template&limit=20"
curl http://127.0.0.1/api/v1/tasks/{task_id}/callbacks
curl http://127.0.0.1/api/v1/tasks/{task_id}/executions
curl http://127.0.0.1/api/v1/executions/{execution_id}
curl "http://127.0.0.1/api/v1/executions?status=failed&source=api"
curl "http://127.0.0.1/api/v1/assets?status=active&freshness_status=stale&limit=50&offset=0"
curl http://127.0.0.1/api/v1/integrations/jumpserver/capabilities
curl http://127.0.0.1/api/v1/integrations/jumpserver/permission-check
curl http://127.0.0.1/api/v1/sync/snapshots/latest
curl "http://127.0.0.1/api/v1/sync/snapshots?limit=20"
curl -X POST http://127.0.0.1/api/v1/admin/sync/assets/{jms_asset_id}/refresh
curl -X POST http://127.0.0.1/api/v1/admin/tasks/{task_id}/refresh-retry
curl -X POST http://127.0.0.1/api/v1/admin/tasks/refresh-retry/batch -H "Content-Type: application/json" -d '{"hours":24,"failure_codes":["ASSET_STALE","ASSET_EXPIRED"],"limit":100,"dry_run":true}'
curl "http://127.0.0.1/api/v1/admin/tasks/refresh-retry/audits?operator_id=alice&limit=20&offset=0"
curl "http://127.0.0.1/api/v1/admin/tasks/refresh-retry/audits/{audit_id}?item_limit=200&item_offset=0"
curl -X POST http://127.0.0.1/api/v1/admin/callback/tick
curl "http://127.0.0.1/api/v1/admin/callback/deliveries?status=dead&error_contains=timeout&limit=50&offset=0"
curl -X POST http://127.0.0.1/api/v1/admin/callback/deliveries/{delivery_id}/replay -H "Content-Type: application/json" -d '{"reset_attempts":true}'
curl -X POST http://127.0.0.1/api/v1/admin/callback/deliveries/replay -H "Content-Type: application/json" -H "X-Operator-Id: your-name" -d '{"status":"dead","error_contains":"timeout","limit":100,"reset_attempts":true}'
curl "http://127.0.0.1/api/v1/admin/callback/replay-audits?operator_id=your-name&limit=20&offset=0"
```

Callback security controls (anti-SSRF + whitelist):

```bash
CALLBACK_REQUIRE_WHITELIST=false
CALLBACK_ALLOWED_HOSTS=
CALLBACK_ALLOWED_DOMAIN_SUFFIXES=
CALLBACK_ALLOWED_CIDRS=
CALLBACK_BLOCK_PRIVATE_NETWORKS=true
CALLBACK_REQUIRE_DNS_RESOLVE=false
CALLBACK_REPLAY_MAX_APPLY=100
```

Notes:

- By default, private/reserved callback targets are blocked.
- Allow specific internal endpoints through whitelist settings.
- Callback signature is sent as `X-OpsPaw-Signature` with timestamp/nonce headers.

Failure summary endpoint (dashboard-ready):

```bash
curl "http://127.0.0.1/api/v1/metrics/failures/summary?hours=24"
curl "http://127.0.0.1/api/v1/metrics/task-retry/summary?hours=24&source=api&include_dry_run=false"
curl "http://127.0.0.1/api/v1/metrics/failures/remediation-template?failure_code=CONNECTIVITY_ERROR"
curl "http://127.0.0.1/api/v1/metrics/failures/remediation-template?failure_code=ASSET_EXPIRED&source=api&risk_level=safe-write"
curl "http://127.0.0.1/api/v1/metrics/failures/remediation-templates"
curl "http://127.0.0.1/api/v1/metrics/failures/remediation?task_id={task_id}"
curl "http://127.0.0.1/api/v1/metrics/preaggregation/status?granularity=hour"
curl "http://127.0.0.1/api/v1/metrics/preaggregation/alerts?granularity=hour"
curl "http://127.0.0.1/api/v1/audits/summary?hours=24&source=api"
curl "http://127.0.0.1/api/v1/dashboard/overview?hours=24&source=api&top_n=5"
curl "http://127.0.0.1/api/v1/dashboard/failures/CONNECTIVITY_ERROR/detail?hours=24&source=api&limit=20"
```

Task query response now includes `failure_code` when `status=failed`.
Known failure codes currently include:

- `UPSTREAM_ERROR`
- `PERMISSION_DENIED`
- `CONNECTIVITY_ERROR`
- `UPSTREAM_BAD_RESPONSE`
- `VALIDATION_ERROR`
- `ASSET_NOT_FOUND`
- `ASSET_INACTIVE`
- `ASSET_STALE`
- `ASSET_EXPIRED`
- `EXECUTION_TIMEOUT`
- `EXECUTION_FAILED`
- `APPROVAL_TIMEOUT`
- `APPROVAL_REJECTED`
- `POLICY_BLOCKED`
- `INTERNAL_ERROR`
- `CANCELED`

When stale/expired gate blocks execution, you can trigger targeted projection refresh:

```bash
curl -X POST http://127.0.0.1/api/v1/admin/sync/assets/{jms_asset_id}/refresh
```

Optional auto-retry mode for stale/expired gate (disabled by default):

```bash
EXECUTION_GATE_AUTO_REFRESH_ENABLED=true
EXECUTION_GATE_REFRESH_SEARCH_LIMIT=20
EXECUTION_GATE_REFRESH_SCAN_PAGES=5
TASK_REFRESH_RETRY_MAX_HOURS=24
TASK_REFRESH_RETRY_SAME_ASSET_MAX_RETRIES=2
TASK_REFRESH_RETRY_WINDOW_SIZE=5
TASK_REFRESH_RETRY_MAX_WINDOWS_PER_REQUEST=2
TASK_REFRESH_RETRY_SCHEDULER_ENABLED=false
TASK_REFRESH_RETRY_SCHEDULER_INTERVAL_SEC=300
TASK_REFRESH_RETRY_SCHEDULER_HOURS=24
TASK_REFRESH_RETRY_SCHEDULER_SOURCE=
TASK_REFRESH_RETRY_SCHEDULER_FAILURE_CODES=ASSET_STALE,ASSET_EXPIRED
TASK_REFRESH_RETRY_SCHEDULER_LIMIT=100
TASK_REFRESH_RETRY_SCHEDULER_WINDOW_SIZE=5
TASK_REFRESH_RETRY_SCHEDULER_MAX_WINDOWS=1
APPROVAL_TIMEOUT_HOURS=24
APPROVAL_EXPIRE_CHECK_INTERVAL_SEC=60
APPROVAL_EXPIRE_BATCH_SIZE=200
APPROVAL_ESCALATION_ENABLED=false
APPROVAL_ESCALATION_AFTER_MINUTES=30
APPROVAL_MAX_LEVELS=2
POLICY_BUILTIN_BLACKLIST=rm -rf /,mkfs,shutdown -h,reboot,poweroff,:(){:|:&};:
```

Operator shortcut for failed gate tasks:

- `POST /api/v1/admin/tasks/{task_id}/refresh-retry`
- Only for failed tasks with failure code in `ASSET_STALE/ASSET_EXPIRED/ASSET_NOT_FOUND/ASSET_INACTIVE`
- Server action: refresh target asset projection once, then immediately trigger orchestrator retry

Batch operator shortcut (recent ASSET_* failed tasks):

- `POST /api/v1/admin/tasks/refresh-retry/batch`
- Supports `task_ids` direct selection or `hours + source + failure_codes` filtering
- Supports `dry_run=true` for impact preview before actual retry
- Enforces guardrails:
  - only recent tasks within effective `hours` (capped by `TASK_REFRESH_RETRY_MAX_HOURS`)
  - same asset retry cap (`TASK_REFRESH_RETRY_SAME_ASSET_MAX_RETRIES`)
  - same task cooldown (`TASK_REFRESH_RETRY_TASK_COOLDOWN_MINUTES`)
  - request-level rate window (`TASK_REFRESH_RETRY_WINDOW_SIZE * TASK_REFRESH_RETRY_MAX_WINDOWS_PER_REQUEST`)

Batch retry audit query:

- `GET /api/v1/admin/tasks/refresh-retry/audits`
- `GET /api/v1/admin/tasks/refresh-retry/audits/{audit_id}`
- `GET /api/v1/admin/tasks/refresh-retry/audits/{audit_id}/export?format=csv|json`
- Records operator/source IP/filter/summaries and per-task actions (`queued/would_retry/skipped_*`)
- `POST /api/v1/admin/metrics/preaggregation/run` (debug only) can rebuild preaggregated buckets immediately

Scheduled batch retry (worker-level, no debug endpoint needed):

- Controlled by `TASK_REFRESH_RETRY_SCHEDULER_*` configs
- Scheduler worker runs the same guarded batch logic and writes the same retry audits
- Keep `TASK_REFRESH_RETRY_SCHEDULER_ENABLED=false` by default; enable only after dry-run verification
- Approval timeout expiry is handled by the same scheduler worker (`APPROVAL_EXPIRE_CHECK_INTERVAL_SEC`, `APPROVAL_EXPIRE_BATCH_SIZE`)
- Approval supports escalation chain (`APPROVAL_ESCALATION_ENABLED`, `APPROVAL_ESCALATION_AFTER_MINUTES`, `APPROVAL_MAX_LEVELS`)
- Metrics preaggregation is controlled by `METRICS_PREAGGREGATION_*` configs (enabled by default)

## Local tests

```bash
pytest -q
```

Run real JumpServer integration test (optional):

```bash
export RUN_JUMPSERVER_INTEGRATION=true
export JUMPSERVER_BASE_URL=http://your-jumpserver
export JUMPSERVER_TOKEN=your_token
pytest -q -m integration
```

## systemd integration

### Docker Compose mode

1. Copy service file.

```bash
sudo cp docker/systemd/opspaw-compose.service /etc/systemd/system/
```

2. Enable service.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now opspaw-compose.service
```

### Bare-metal API mode (venv + uvicorn)

1. Copy service file.

```bash
sudo cp docker/systemd/opspaw-api.service /etc/systemd/system/
```

2. Enable service.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now opspaw-api.service
sudo systemctl status opspaw-api.service
```

### Bare-metal workers mode (recommended)

1. Copy worker service files.

```bash
sudo cp docker/systemd/opspaw-orchestrator.service /etc/systemd/system/
sudo cp docker/systemd/opspaw-sync.service /etc/systemd/system/
sudo cp docker/systemd/opspaw-callback.service /etc/systemd/system/
sudo cp docker/systemd/opspaw-scheduler.service /etc/systemd/system/
```

2. Enable workers.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now opspaw-orchestrator.service
sudo systemctl enable --now opspaw-sync.service
sudo systemctl enable --now opspaw-callback.service
sudo systemctl enable --now opspaw-scheduler.service
sudo systemctl status opspaw-orchestrator.service
sudo systemctl status opspaw-sync.service
```

## Next implementation priorities

- Add execution override workflow for stale/expired asset gate (approval + audit).
- Add approval/policy gates before execution.
- Add callback audit retention/export and operator-level access control.
