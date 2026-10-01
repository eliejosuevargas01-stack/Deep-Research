import asyncio
import ipaddress
import socket
from urllib.parse import urlparse
from aiohttp.abc import AbstractResolver


class SSRFSecurityViolation(ValueError):
    pass


class PinnedResolver(AbstractResolver):
    """Resolve once per connection and return only validated public addresses."""

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC):
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        results = []
        for resolved_family, _, proto, _, address in infos:
            raw = str(address[0])
            _validate_ip(raw)
            results.append({"hostname": host, "host": raw, "port": port, "family": resolved_family, "proto": proto, "flags": 0})
        if not results:
            raise SSRFSecurityViolation("URL host does not resolve")
        return results

    async def close(self):
        return None


def _validate_ip(raw: str) -> None:
    ip = ipaddress.ip_address(raw)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        raise SSRFSecurityViolation("Private or reserved destination blocked")


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SSRFSecurityViolation("Only absolute HTTP(S) URLs are allowed")
    if parsed.port and parsed.port not in {80, 443}:
        raise SSRFSecurityViolation("Non-standard ports are not allowed")
    try:
        addresses = {str(item[4][0]) for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise SSRFSecurityViolation("URL host does not resolve") from exc
    if not addresses:
        raise SSRFSecurityViolation("URL host does not resolve")
    for raw in addresses:
        _validate_ip(raw)
    return url
