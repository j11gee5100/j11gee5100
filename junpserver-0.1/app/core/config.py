from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OpsPaw"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    app_log_level: str = "INFO"

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+psycopg://opspaw:opspaw@postgres:5432/opspaw"
    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "opspaw-artifacts"

    worker_poll_interval_sec: int = 10
    callback_retry_interval_sec: int = 30
    callback_http_timeout_sec: int = 10
    callback_max_attempts: int = 8
    callback_retry_base_sec: int = 5
    callback_batch_size: int = 20
    callback_require_whitelist: bool = False
    callback_allowed_hosts: str = ""
    callback_allowed_domain_suffixes: str = ""
    callback_allowed_cidrs: str = ""
    callback_block_private_networks: bool = True
    callback_require_dns_resolve: bool = False
    callback_replay_max_apply: int = 100
    scheduler_tick_interval_sec: int = 15
    jumpserver_sync_page_size: int = 50
    app_allow_admin_debug_endpoints: bool = False

    jumpserver_base_url: str = "http://127.0.0.1:8080"
    jumpserver_token: str = ""
    jumpserver_timeout_sec: int = 15
    jumpserver_verify_tls: bool = True
    jumpserver_execution_timeout_sec: int = 600
    jumpserver_incremental_updated_at_param: str = "updated_at__gte"
    sync_incremental_strategy: str = "auto"
    sync_incremental_initial_lookback_hours: int = 24
    sync_timestamp_ineffective_threshold: int = 3
    sync_timestamp_force_full_minutes: int = 30
    sync_asset_fresh_minutes: int = 30
    sync_asset_stale_hours: int = 6
    sync_inactivation_guardrail_ratio: float = 0.2
    sync_inactivation_guardrail_max: int = 500
    sync_consistency_warn_delta_assets: int = 3
    sync_consistency_freshness_hours: int = 24
    execution_gate_auto_refresh_enabled: bool = False
    execution_gate_refresh_search_limit: int = 20
    execution_gate_refresh_scan_pages: int = 5
    task_refresh_retry_max_hours: int = 24
    task_refresh_retry_same_asset_max_retries: int = 2
    task_refresh_retry_task_cooldown_minutes: int = 30
    task_refresh_retry_window_size: int = 5
    task_refresh_retry_max_windows_per_request: int = 2
    task_refresh_retry_scheduler_enabled: bool = False
    task_refresh_retry_scheduler_interval_sec: int = 300
    task_refresh_retry_scheduler_hours: int = 24
    task_refresh_retry_scheduler_source: str = ""
    task_refresh_retry_scheduler_failure_codes: str = "ASSET_STALE,ASSET_EXPIRED"
    task_refresh_retry_scheduler_limit: int = 100
    task_refresh_retry_scheduler_window_size: int = 5
    task_refresh_retry_scheduler_max_windows: int = 1
    approval_timeout_hours: int = 24
    approval_expire_check_interval_sec: int = 60
    approval_expire_batch_size: int = 200
    approval_escalation_enabled: bool = False
    approval_escalation_after_minutes: int = 30
    approval_max_levels: int = 2
    policy_builtin_blacklist: str = "rm -rf /,mkfs,shutdown -h,reboot,poweroff,:(){:|:&};:"
    metrics_preaggregation_scheduler_enabled: bool = True
    metrics_preaggregation_interval_sec: int = 300
    metrics_preaggregation_hourly_lookback_hours: int = 72
    metrics_preaggregation_daily_lookback_days: int = 30
    metrics_preaggregation_max_lag_minutes: int = 30
    mcp_enabled: bool = True
    mcp_read_only: bool = False
    mcp_toolsets: str = "profiles,packages_read,bundles_read,audit,packages_write,probe,bundles_write"
    mcp_allowed_package_roots: str = "/mnt/env-packages,/nas/inference-packages,/data/env-packages"
    mcp_client_public_base_url: str = ""
    env_package_upload_root: str = "/data/env-packages"
    delivery_bundle_artifact_root: str = "/tmp/opspaw-delivery-bundles"
    auth_token_secret: str = "opspaw-dev-secret-change-me"
    auth_token_ttl_hours: int = 12

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
