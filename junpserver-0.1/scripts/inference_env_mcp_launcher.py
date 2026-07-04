#!/usr/bin/env python3
"""OpsPaw Inference Env MCP stdio launcher with safe auto-update.

Codex/Agent config should point to this launcher, not directly to the generated
stdio adapter. On each startup it fetches the server manifest, verifies sha256,
caches the latest adapter locally, and then execs it.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request

BASE_URL = os.environ.get("INFERENCE_ENV_MCP_BASE_URL", "http://127.0.0.1:18080").rstrip("/")
CACHE_DIR = Path(os.environ.get("INFERENCE_ENV_MCP_CLIENT_CACHE", "~/.cache/opspaw/inference-env-mcp")).expanduser()
DISABLE_UPDATE = os.environ.get("INFERENCE_ENV_MCP_AUTO_UPDATE", "1").lower() in {"0", "false", "no", "off"}
TIMEOUT_SEC = float(os.environ.get("INFERENCE_ENV_MCP_UPDATE_TIMEOUT_SEC", "10"))
LOCAL_FALLBACK = Path(__file__).with_name("inference_env_mcp_stdio.py")


def _log(message: str) -> None:
    # MCP stdio reserves stdout for JSON-RPC. Diagnostics must go to stderr.
    print(f"[opspaw-mcp-launcher] {message}", file=sys.stderr, flush=True)


def _http_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as resp:
        return resp.read()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_valid_python_script(path: Path, expected_sha256: str) -> bool:
    if not path.exists() or not path.is_file():
        return False
    data = path.read_bytes()
    if expected_sha256 and _sha256(data) != expected_sha256:
        return False
    return data.startswith(b"#!/usr/bin/env python") or b"def main()" in data[:4096]


def resolve_client() -> Path:
    if DISABLE_UPDATE:
        _log("auto update disabled; using local fallback")
        return LOCAL_FALLBACK
    try:
        manifest_url = f"{BASE_URL}/mcp/client/manifest"
        manifest = _http_get_json(manifest_url)
        version = str(manifest.get("version") or "latest")
        sha256 = str(manifest.get("sha256") or "")
        download_url = str(manifest.get("download_url") or "")
        if download_url.startswith("/"):
            download_url = f"{BASE_URL}{download_url}"
        if not sha256 or not download_url:
            raise RuntimeError(f"invalid manifest: {manifest}")

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = CACHE_DIR / f"inference_env_mcp_stdio-{version}-{sha256[:12]}.py"
        current = CACHE_DIR / "inference_env_mcp_stdio.py"
        if _is_valid_python_script(current, sha256):
            return current
        if _is_valid_python_script(target, sha256):
            current.write_bytes(target.read_bytes())
            current.chmod(0o755)
            return current

        data = _http_get_bytes(download_url)
        got = _sha256(data)
        if got != sha256:
            raise RuntimeError(f"sha256 mismatch: expected {sha256}, got {got}")
        if b"TOKEN" not in data[:20000] or b"def main()" not in data:
            raise RuntimeError("downloaded client does not look like OpsPaw stdio adapter")

        fd, tmp_name = tempfile.mkstemp(prefix="opspaw-mcp-", suffix=".py", dir=str(CACHE_DIR))
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)
        tmp_path = Path(tmp_name)
        tmp_path.chmod(0o755)
        tmp_path.replace(target)
        current.write_bytes(data)
        current.chmod(0o755)
        _log(f"updated stdio client to version={version} sha256={sha256[:12]}")
        return current
    except Exception as exc:
        _log(f"auto update failed: {exc}; using local fallback")
        return LOCAL_FALLBACK


def main() -> int:
    client = resolve_client()
    if not client.exists():
        _log(f"client not found: {client}")
        return 127
    os.execv(sys.executable, [sys.executable, str(client), *sys.argv[1:]])
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
