from __future__ import annotations

import pytest

from src.multimodal.url_reader import SSRFGuard, URLSecurityError


def test_guard_rejects_non_http_scheme() -> None:
    guard = SSRFGuard()
    with pytest.raises(URLSecurityError):
        guard.check_scheme("file:///etc/passwd")
    with pytest.raises(URLSecurityError):
        guard.check_scheme("ftp://example.com/file")
    with pytest.raises(URLSecurityError):
        guard.check_scheme("javascript:alert(1)")
    with pytest.raises(URLSecurityError):
        guard.check_scheme("gopher://example.com/")


def test_guard_accepts_http_and_https() -> None:
    guard = SSRFGuard()
    guard.check_scheme("http://example.com")
    guard.check_scheme("https://example.com")


def test_guard_blocks_private_ipv4() -> None:
    guard = SSRFGuard()
    for ip in ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1"]:
        with pytest.raises(URLSecurityError):
            guard.check_ip(ip)


def test_guard_blocks_link_local() -> None:
    guard = SSRFGuard()
    with pytest.raises(URLSecurityError):
        guard.check_ip("169.254.169.254")  # AWS metadata


def test_guard_blocks_loopback_ipv6() -> None:
    guard = SSRFGuard()
    with pytest.raises(URLSecurityError):
        guard.check_ip("::1")
    with pytest.raises(URLSecurityError):
        guard.check_ip("fe80::1")


def test_guard_accepts_public_ip() -> None:
    guard = SSRFGuard()
    guard.check_ip("8.8.8.8")
    guard.check_ip("1.1.1.1")
