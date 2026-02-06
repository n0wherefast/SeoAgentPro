"""
URL validation utilities with SSRF prevention.
"""

import ipaddress
import re
from urllib.parse import urlparse


# Allowed URL schemes
_ALLOWED_SCHEMES = {"http", "https"}

# Regex for basic URL format validation
_URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


def validate_url(url: str) -> str:
    """
    Validates a URL and prevents SSRF attacks.

    Args:
        url: The URL string to validate.

    Returns:
        The validated URL string (stripped).

    Raises:
        ValueError: If the URL is invalid or points to a private/reserved IP.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL is required and must be a non-empty string.")

    url = url.strip()

    # Check scheme
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are allowed."
        )

    # Check hostname presence
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must contain a valid hostname.")

    # Block private / reserved IPs (SSRF prevention)
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            raise ValueError(
                f"Access to private/reserved IP addresses is not allowed: {hostname}"
            )
    except ValueError as ve:
        # If it's our own ValueError, re-raise
        if "private" in str(ve).lower() or "reserved" in str(ve).lower():
            raise
        # Otherwise hostname is not an IP — that's fine, it's a domain name
        pass

    # Basic URL format check
    if not _URL_PATTERN.match(url):
        raise ValueError(f"Invalid URL format: {url}")

    return url


def sanitize_url(url: str) -> str:
    """
    Sanitize a URL by stripping whitespace and ensuring it starts with http(s)://.
    Does not raise — returns the url as-is if it looks valid, or prepends https://.
    """
    if not url or not isinstance(url, str):
        return url

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url
