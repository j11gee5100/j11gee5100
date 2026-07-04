from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.core.trace import get_trace_id
from app.services.jumpserver.schemas import Asset, CommandExecutionRequest, CommandExecutionResponse, SystemUser


logger = logging.getLogger("opspaw.jumpserver")


class JumpServerClientError(Exception):
    """Raised when JumpServer API returns unexpected results."""


class JumpServerClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout_sec: int | None = None,
        verify_tls: bool | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or settings.jumpserver_base_url).rstrip("/")
        self.token = token if token is not None else settings.jumpserver_token
        self.timeout_sec = timeout_sec or settings.jumpserver_timeout_sec
        self.verify_tls = (
            verify_tls if verify_tls is not None else settings.jumpserver_verify_tls
        )
        self._client = client
        self._api_mode: str | None = None

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        trace_id = get_trace_id()
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        return headers

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._build_headers()
        client = self._client or httpx.Client(
            timeout=self.timeout_sec, verify=self.verify_tls
        )

        should_close = self._client is None
        try:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
            )
        except httpx.HTTPError as exc:
            raise JumpServerClientError(f"http error calling {path}: {exc}") from exc
        finally:
            if should_close:
                client.close()

        if response.status_code >= 400:
            raise JumpServerClientError(
                f"jumpserver {method} {path} failed status={response.status_code} body={response.text}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise JumpServerClientError(
                f"jumpserver {method} {path} returned non-json response"
            ) from exc

    @staticmethod
    def _is_http_status_error(exc: JumpServerClientError, status_code: int) -> bool:
        return f"status={status_code}" in str(exc)

    def _detect_api_mode(self) -> str:
        if self._api_mode:
            return self._api_mode

        try:
            self._request(
                "GET",
                "/api/v1/perms/users/assets/",
                params={"limit": 1, "offset": 0},
            )
            self._api_mode = "legacy_v3"
            return self._api_mode
        except JumpServerClientError as exc:
            if not self._is_http_status_error(exc, 404):
                raise

        try:
            self._request(
                "GET",
                "/api/v1/perms/users/my/assets/",
                params={"limit": 1, "offset": 0},
            )
            self._api_mode = "v4"
            return self._api_mode
        except JumpServerClientError as exc:
            if self._is_http_status_error(exc, 403):
                self._api_mode = "v4"
                return self._api_mode
            if not self._is_http_status_error(exc, 404):
                raise

        try:
            self._request(
                "GET",
                "/api/v1/assets/assets/",
                params={"limit": 1, "offset": 0},
            )
            self._api_mode = "v4"
            return self._api_mode
        except JumpServerClientError as exc:
            if self._is_http_status_error(exc, 403):
                self._api_mode = "v4"
                return self._api_mode
            raise JumpServerClientError(
                "failed to detect jumpserver api mode"
            ) from exc

    def get_api_mode(self) -> str:
        return self._detect_api_mode()

    @staticmethod
    def _extract_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, list):
                return results
            if "data" in payload and isinstance(payload["data"], list):
                return payload["data"]
        return []

    @staticmethod
    def _extract_total(payload: Any) -> int | None:
        if isinstance(payload, dict):
            raw_total = payload.get("count")
            if isinstance(raw_total, int):
                return raw_total
        return None

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        try:
            uuid.UUID(value)
            return True
        except Exception:
            return False

    def list_assets(
        self, search: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Asset]:
        assets, _total = self.list_assets_page(search=search, limit=limit, offset=offset)
        return assets

    def list_assets_page(
        self,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        extra_params: dict[str, Any] | None = None,
    ) -> tuple[list[Asset], int | None]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if extra_params:
            params.update(extra_params)
        mode = self._detect_api_mode()
        if mode == "legacy_v3":
            payload = self._request("GET", "/api/v1/perms/users/assets/", params=params)
        else:
            from_my_assets = False
            try:
                payload = self._request("GET", "/api/v1/perms/users/my/assets/", params=params)
                from_my_assets = True
            except JumpServerClientError as exc:
                if not self._is_http_status_error(exc, 404):
                    raise
                payload = self._request("GET", "/api/v1/assets/assets/", params=params)

            if from_my_assets:
                items_from_my = self._extract_items(payload)
                total_from_my = self._extract_total(payload)
                if not items_from_my and total_from_my in (0, None):
                    try:
                        payload = self._request("GET", "/api/v1/assets/assets/", params=params)
                    except JumpServerClientError as exc:
                        if not (self._is_http_status_error(exc, 403) or self._is_http_status_error(exc, 404)):
                            raise
        items = self._extract_items(payload)
        normalized_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            if not normalized.get("hostname"):
                normalized["hostname"] = normalized.get("name", "")
            if not normalized.get("ip"):
                normalized["ip"] = normalized.get("address", "")
            if not normalized.get("updated_at"):
                normalized["updated_at"] = (
                    normalized.get("date_updated")
                    or normalized.get("updated")
                    or normalized.get("modified")
                    or ""
                )
            normalized_items.append(normalized)
        total = self._extract_total(payload)
        return [Asset.model_validate(item) for item in normalized_items], total

    def list_assets_updated_since_page(
        self,
        *,
        updated_since: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Asset], int | None]:
        requested_key = (settings.jumpserver_incremental_updated_at_param or "").strip()
        candidates = [
            requested_key,
            "updated_at__gte",
            "updated_at__gt",
            "date_updated__gte",
            "date_updated__gt",
            "updated_after",
        ]
        deduped_keys: list[str] = []
        for key in candidates:
            key_norm = (key or "").strip()
            if not key_norm or key_norm in deduped_keys:
                continue
            deduped_keys.append(key_norm)

        last_exc: JumpServerClientError | None = None
        for key in deduped_keys:
            try:
                return self.list_assets_page(
                    limit=limit,
                    offset=offset,
                    extra_params={key: updated_since},
                )
            except JumpServerClientError as exc:
                if self._is_http_status_error(exc, 400) or self._is_http_status_error(exc, 404):
                    last_exc = exc
                    continue
                raise

        message = f"jumpserver incremental sync by updated_at unsupported: tried params={deduped_keys}"
        if last_exc:
            message = f"{message}, last_error={last_exc}"
        raise JumpServerClientError(message)

    def list_asset_system_users(self, asset_id: str) -> list[SystemUser]:
        mode = self._detect_api_mode()
        if mode == "legacy_v3":
            path = f"/api/v1/perms/users/assets/{asset_id}/system-users/"
            payload = self._request("GET", path)
            items = self._extract_items(payload)
            return [SystemUser.model_validate(item) for item in items]

        offset = 0
        limit = 200
        all_items: list[dict[str, Any]] = []
        while True:
            payload = self._request(
                "GET",
                "/api/v1/accounts/accounts/",
                params={"asset_id": asset_id, "limit": limit, "offset": offset},
            )
            items = self._extract_items(payload)
            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = {
                    "id": item.get("id", ""),
                    "name": item.get("name") or item.get("username") or "",
                    "username": item.get("username") or item.get("name") or "",
                }
                all_items.append(normalized)
            if len(items) < limit:
                break
            offset += len(items)
        return [SystemUser.model_validate(item) for item in all_items]

    def create_command_execution(
        self, request: CommandExecutionRequest
    ) -> CommandExecutionResponse:
        mode = self._detect_api_mode()
        if mode == "legacy_v3":
            payload = self._request(
                "POST", "/api/v1/ops/command-executions/", json_body=request.model_dump()
            )
            return CommandExecutionResponse.model_validate(payload)

        run_as = request.run_as
        primary_asset = request.hosts[0] if request.hosts else ""
        if primary_asset and run_as and self._looks_like_uuid(run_as):
            try:
                users = self.list_asset_system_users(primary_asset)
                mapped = next((u.username for u in users if u.id == run_as), "")
                if mapped:
                    run_as = mapped
            except JumpServerClientError:
                pass

        body = {
            "instant": True,
            "is_periodic": False,
            "type": "adhoc",
            "module": "shell",
            "args": request.command,
            "assets": request.hosts,
            "runas": run_as,
            "runas_policy": "privileged_first",
            "comment": "created by opspaw",
        }
        payload = self._request("POST", "/api/v1/ops/jobs/", json_body=body)
        execution_id = ""
        if isinstance(payload, dict):
            raw_task = payload.get("task_id")
            if isinstance(raw_task, str):
                execution_id = raw_task
            elif isinstance(payload.get("id"), str):
                execution_id = payload["id"]
        if not execution_id:
            raise JumpServerClientError("jumpserver v4 job execution id is empty")
        return CommandExecutionResponse(
            id=execution_id,
            is_finished=False,
            result=payload,
            log_url=f"/api/v1/ops/ansible/job-execution/{execution_id}/log/",
        )

    def get_command_execution(self, execution_id: str) -> CommandExecutionResponse:
        mode = self._detect_api_mode()
        if mode == "legacy_v3":
            path = f"/api/v1/ops/command-executions/{execution_id}/"
            payload = self._request("GET", path)
            return CommandExecutionResponse.model_validate(payload)

        try:
            task_detail = self._request(
                "GET",
                f"/api/v1/ops/job-execution/task-detail/{execution_id}/",
            )
            if isinstance(task_detail, dict):
                return CommandExecutionResponse(
                    id=execution_id,
                    is_finished=bool(task_detail.get("is_finished", False)),
                    result=task_detail,
                    log_url=f"/api/v1/ops/ansible/job-execution/{execution_id}/log/",
                )
        except JumpServerClientError as exc:
            if not self._is_http_status_error(exc, 404):
                raise

        payload = self._request("GET", f"/api/v1/ops/job-executions/{execution_id}/")
        is_finished = False
        if isinstance(payload, dict):
            is_finished = bool(payload.get("is_finished", False))
        return CommandExecutionResponse(
            id=execution_id,
            is_finished=is_finished,
            result=payload,
            log_url=f"/api/v1/ops/ansible/job-execution/{execution_id}/log/",
        )

    def list_command_executions(self, limit: int = 50, offset: int = 0) -> Any:
        params = {"limit": limit, "offset": offset}
        mode = self._detect_api_mode()
        if mode == "legacy_v3":
            return self._request("GET", "/api/v1/ops/command-executions/", params=params)
        payload = self._request("GET", "/api/v1/ops/job-executions/", params=params)
        if not isinstance(payload, dict):
            return payload
        results = payload.get("results")
        if not isinstance(results, list):
            return payload
        converted: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            converted.append(
                {
                    "id": item.get("id", ""),
                    "is_finished": bool(item.get("is_finished", False)),
                    "result": item.get("summary", {}),
                }
            )
        return {
            "count": payload.get("count", len(converted)),
            "next": payload.get("next"),
            "previous": payload.get("previous"),
            "results": converted,
        }

    def get_celery_task_log(self, task_id: str) -> Any:
        path = f"/api/v1/ops/celery/task/{task_id}/log/"
        return self._request("GET", path)

    def get_celery_task_result(self, task_id: str) -> Any:
        path = f"/api/v1/ops/celery/task/{task_id}/result/"
        return self._request("GET", path)

    def get_health(self) -> Any:
        return self._request("GET", "/api/v1/health/")

    def get_public_settings(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/v1/settings/public/")
        if isinstance(payload, dict):
            return payload
        raise JumpServerClientError("jumpserver GET /api/v1/settings/public/ returned invalid payload")

    def list_audit_relations(self, limit: int = 50, offset: int = 0) -> Any:
        params = {"limit": limit, "offset": offset}
        return self._request(
            "GET", "/api/v1/audits/command-executions-hosts-relations/", params=params
        )
