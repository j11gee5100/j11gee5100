from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.core.config import settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class CallbackUrlPolicyResult:
    allowed: bool
    reason: str
    resolved_ips: tuple[str, ...] = ()


def _split_csv(raw: str) -> list[str]:
    items: list[str] = []
    for part in (raw or "").split(","):
        item = part.strip().lower()
        if item:
            items.append(item)
    return items


def _normalize_domain_suffixes(raw: str) -> list[str]:
    suffixes: list[str] = []
    for suffix in _split_csv(raw):
        normalized = suffix.lstrip(".")
        if normalized:
            suffixes.append(normalized)
    return suffixes


def _parse_cidrs(raw: str) -> list[IPNetwork]:
    cidrs: list[IPNetwork] = []
    for cidr in _split_csv(raw):
        try:
            cidrs.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            continue
    return cidrs


def _host_matches(host: str, allowed_hosts: set[str], allowed_suffixes: list[str]) -> bool:
    if host in allowed_hosts:
        return True
    for suffix in allowed_suffixes:
        if host == suffix or host.endswith(f".{suffix}"):
            return True
    return False


def _is_private_like(ip: IPAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _ip_in_cidrs(ip: IPAddress, cidrs: list[IPNetwork]) -> bool:
    for network in cidrs:
        if ip.version != network.version:
            continue
        if ip in network:
            return True
    return False


def _resolve_ips(host: str, port: int) -> tuple[set[IPAddress], str | None]:
    try:
        addrinfos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return set(), str(exc)
    resolved: set[IPAddress] = set()
    for info in addrinfos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        raw_ip = sockaddr[0]
        try:
            resolved.add(ipaddress.ip_address(raw_ip))
        except ValueError:
            continue
    return resolved, None


def evaluate_callback_url_policy(url: str, *, resolve_dns: bool) -> CallbackUrlPolicyResult:
    raw = (url or "").strip()
    if not raw:
        return CallbackUrlPolicyResult(False, "callback_url is empty")

    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        return CallbackUrlPolicyResult(False, f"invalid callback_url: {exc}")

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return CallbackUrlPolicyResult(False, "callback_url must use http:// or https://")

    if parsed.username or parsed.password:
        return CallbackUrlPolicyResult(False, "callback_url must not include credentials")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        return CallbackUrlPolicyResult(False, "callback_url host is required")

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError:
        return CallbackUrlPolicyResult(False, "callback_url port is invalid")

    allowed_hosts = set(_split_csv(settings.callback_allowed_hosts))
    allowed_suffixes = _normalize_domain_suffixes(settings.callback_allowed_domain_suffixes)
    allowed_cidrs = _parse_cidrs(settings.callback_allowed_cidrs)
    whitelist_configured = bool(allowed_hosts or allowed_suffixes or allowed_cidrs)

    if settings.callback_require_whitelist and not whitelist_configured:
        return CallbackUrlPolicyResult(False, "callback whitelist is required but empty")

    host_whitelisted = _host_matches(host, allowed_hosts, allowed_suffixes)
    known_ips: set[IPAddress] = set()

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        known_ips.add(literal_ip)

    need_dns = resolve_dns and literal_ip is None and (
        settings.callback_block_private_networks or bool(allowed_cidrs)
    )
    if need_dns:
        resolved, resolve_error = _resolve_ips(host, port)
        if resolve_error and settings.callback_require_dns_resolve:
            return CallbackUrlPolicyResult(False, f"callback_url DNS resolve failed: {resolve_error}")
        known_ips.update(resolved)

    ip_whitelisted = any(_ip_in_cidrs(ip, allowed_cidrs) for ip in known_ips)
    whitelisted = host_whitelisted or ip_whitelisted

    if whitelist_configured and not whitelisted:
        return CallbackUrlPolicyResult(False, "callback_url is not in whitelist")

    if settings.callback_block_private_networks:
        if host in {"localhost", "localhost.localdomain"} and not whitelisted:
            return CallbackUrlPolicyResult(False, "callback_url host localhost is blocked")
        for ip in known_ips:
            if _is_private_like(ip) and not _ip_in_cidrs(ip, allowed_cidrs) and not host_whitelisted:
                return CallbackUrlPolicyResult(False, f"callback_url target {ip} is private or reserved")

    return CallbackUrlPolicyResult(
        True,
        "allowed",
        tuple(sorted(str(item) for item in known_ips)),
    )
