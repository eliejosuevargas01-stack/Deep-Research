from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import ipaddress
import os
import socket
from urllib.parse import urlparse
from app.core.config import settings
from app.models import AppSettings
from app.schemas import PROVIDERS, ROLES
from app.services.crypto import decrypt_secret, encrypt_secret, mask_secret

_FORBIDDEN_METADATA_IPS = {
    "169.254.169.254",
    "169.254.170.2",
    "100.100.100.200",  # Alibaba Cloud ECS metadata
    "fd00:ec2::254",    # AWS IPv6 IMDS
}

_BLOCKED_BASE_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "::",
    "169.254.169.254",
    "169.254.170.2",
    "100.100.100.200",
    "fd00:ec2::254",
    "metadata.google.internal",
    "instance-data",
    "metadata.titus.netflix.com",
}


def is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if IP is loopback, link-local, multicast, unspecified, or cloud metadata.
    These destinations are strictly forbidden and NEVER permitted (even if in allowlist).
    """
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped:
        ip = mapped
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or str(ip).lower() in _FORBIDDEN_METADATA_IPS
    )


def get_trusted_router_hosts() -> set[str]:
    """Retrieve administratively configured trusted router hosts.

    No hardcoded hosts (removes implicit trust for 9router.internal, custom-openai.internal, litellm).
    LITELLM_API_BASE is NOT auto-trusted. Only explicit administrative config is accepted.
    Loopback, link-local, and metadata destinations are NEVER trusted.
    """
    hosts: set[str] = set()
    env_hosts = os.environ.get("TRUSTED_ROUTER_HOSTS")
    if env_hosts:
        hosts.update(h.strip().lower() for h in env_hosts.split(",") if h.strip())
    trusted_from_settings = getattr(settings, "TRUSTED_ROUTER_HOSTS", None)
    if trusted_from_settings:
        hosts.update(h.strip().lower() for h in str(trusted_from_settings).split(",") if h.strip())

    sanitized: set[str] = set()
    for h in hosts:
        clean = h.strip("[]")
        if clean in _BLOCKED_BASE_HOSTS or clean.endswith(".localhost"):
            continue
        try:
            ip = ipaddress.ip_address(clean)
            if is_forbidden_ip(ip):
                continue
        except ValueError:
            pass
        sanitized.add(h)
    return sanitized


def validate_base_url(url: str | None) -> str | None:
    """Validate base_url against SSRF (metadata, loopback, and untrusted private destinations)."""
    if not url:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Invalid base_url: scheme must be http or https")
    if not parsed.hostname:
        raise ValueError("Invalid base_url: hostname required")
    if parsed.username or parsed.password:
        raise ValueError("Invalid base_url: credentials in URL are prohibited")
    if parsed.query:
        raise ValueError("Invalid base_url: query parameters are prohibited")
    if parsed.fragment:
        raise ValueError("Invalid base_url: fragment identifiers are prohibited")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ValueError("Invalid base_url: port must be between 1 and 65535")

    host_lower = parsed.hostname.lower().strip("[]")
    if host_lower in _BLOCKED_BASE_HOSTS or host_lower.endswith(".localhost"):
        raise ValueError(f"Invalid base_url: loopback and metadata hosts are blocked ({host_lower})")

    # Check if host is raw IP literal
    try:
        raw_ip = ipaddress.ip_address(host_lower)
        mapped = getattr(raw_ip, "ipv4_mapped", None)
        effective_ip = mapped if mapped else raw_ip
        if is_forbidden_ip(effective_ip):
            raise ValueError(f"Invalid base_url: loopback, link-local, or metadata IP blocked ({raw_ip})")
        if not effective_ip.is_global:
            if effective_ip.is_private:
                trusted = get_trusted_router_hosts()
                if host_lower not in trusted and str(raw_ip) not in trusted and str(effective_ip) not in trusted:
                    raise ValueError(f"Invalid base_url: untrusted private IP blocked ({raw_ip})")
            else:
                raise ValueError(f"Invalid base_url: non-global IP blocked ({raw_ip})")
        return cleaned
    except ValueError as e:
        if "Invalid base_url" in str(e):
            raise

    # Try DNS resolution to detect loopback/metadata/non-global/private IPs.
    # Note: Preflight DNS check validates current resolution; complete immunity against
    # runtime DNS rebinding (TOCTOU) requires connection-level socket pinning or egress firewall.
    trusted = get_trusted_router_hosts()
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = socket.getaddrinfo(host_lower, port, type=socket.SOCK_STREAM)
        for _, _, _, _, addr in infos:
            ip_str = addr[0]
            raw_ip = ipaddress.ip_address(ip_str)
            mapped = getattr(raw_ip, "ipv4_mapped", None)
            effective_ip = mapped if mapped else raw_ip
            if is_forbidden_ip(effective_ip):
                raise ValueError(f"Invalid base_url: host resolves to blocked IP ({raw_ip})")
            if not effective_ip.is_global:
                if effective_ip.is_private:
                    if host_lower not in trusted and ip_str not in trusted and str(effective_ip) not in trusted:
                        raise ValueError(f"Invalid base_url: host resolves to untrusted private IP ({raw_ip})")
                else:
                    raise ValueError(f"Invalid base_url: host resolves to non-global IP ({raw_ip})")
    except socket.gaierror:
        # If domain cannot be resolved and ends in internal TLD, reject unless in trusted config
        if host_lower.endswith((".internal", ".local", ".lan", ".home", ".corp")):
            if host_lower not in trusted:
                raise ValueError(f"Invalid base_url: unverified internal host blocked ({host_lower})")

    return cleaned

ENV_KEYS = {
    "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY",
    "litellm": "LITELLM_API_KEY", "jina": "JINA_API_KEY", "serpapi": "SERPAPI_API_KEY",
    "apify": "APIFY_API_TOKEN",
}


async def get_record(db: AsyncSession) -> AppSettings:
    record = await db.get(AppSettings, 1)
    if not record:
        record = AppSettings(id=1, encrypted_credentials={}, models={}, callback_url=None, openai_base_url=None)
        db.add(record)
        await db.flush()
    return record


async def runtime_settings(db: AsyncSession) -> tuple[dict[str, str], dict[str, str]]:
    record = await get_record(db)
    keys = {}
    for provider in PROVIDERS:
        encrypted = record.encrypted_credentials.get(provider)
        env_value = getattr(settings, ENV_KEYS[provider], None)
        if encrypted:
            keys[provider] = decrypt_secret(encrypted)
        elif env_value:
            keys[provider] = env_value
    models = {role: record.models.get(role) or getattr(settings, f"{role.upper()}_MODEL", None) for role in ROLES}
    return keys, {role: model for role, model in models.items() if model}


async def public_settings(db: AsyncSession) -> dict:
    record = await get_record(db)
    keys, models = await runtime_settings(db)
    return {
        "provider_keys": {p: mask_secret(keys[p]) if p in keys else None for p in PROVIDERS},
        "provider_configured": {p: p in keys for p in PROVIDERS},
        "models": {role: models.get(role) for role in ROLES},
        "callback_url": record.callback_url,
        "openai_base_url": record.openai_base_url,
    }


_UNSET = object()


async def update_settings(
    db: AsyncSession,
    provider_keys: dict,
    models: dict,
    callback_url: str | None | object = _UNSET,
    openai_base_url: str | None | object = _UNSET,
) -> dict:
    record = await get_record(db)
    encrypted = dict(record.encrypted_credentials)
    for provider, value in provider_keys.items():
        if value is None or value == "":
            encrypted.pop(provider, None)
        elif "*" not in value:
            encrypted[provider] = encrypt_secret(value)
    merged_models = dict(record.models)
    merged_models.update(models)
    record.encrypted_credentials = encrypted
    record.models = merged_models
    if callback_url is not _UNSET:
        if callback_url is None:
            record.callback_url = None
        else:
            cleaned_callback = callback_url.strip() if isinstance(callback_url, str) else ""
            if cleaned_callback:
                from app.tools.outbound import validate_public_url
                validate_public_url(cleaned_callback)
                record.callback_url = cleaned_callback
            else:
                record.callback_url = None
    if openai_base_url is not _UNSET:
        if openai_base_url is None:
            record.openai_base_url = None
        else:
            cleaned_base = openai_base_url.strip() if isinstance(openai_base_url, str) else ""
            if cleaned_base:
                validate_base_url(cleaned_base)
                record.openai_base_url = cleaned_base
            else:
                record.openai_base_url = None
    await db.commit()
    return await public_settings(db)
