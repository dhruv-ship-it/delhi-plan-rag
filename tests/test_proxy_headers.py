"""Tests for reading the client address behind a reverse proxy (D-113).

Every case of `TRUSTED_PROXY_HOPS`, because the per-IP rate limit is only a per-IP limit
if this reads the right entry of `X-Forwarded-For`, and reading the wrong one is either
"everyone behind the proxy shares one bucket" (the socket peer) or "anyone can forge a
bucket" (the left-most entry).

These are pure functions over a header string, so nothing here needs the index, a server
or a request - which is the point of their being functions, and is why they run in CI
where `tests/test_api.py` is deselected for want of data.
"""

import pytest

from app.api import forwarded_client_ip, parse_forwarded_entry


@pytest.mark.parametrize(
    "entry,expected",
    [
        ("203.0.113.5", "203.0.113.5"),
        # Azure App Service appends the client's port to the address
        ("203.0.113.5:51234", "203.0.113.5"),
        ("  203.0.113.5:51234  ", "203.0.113.5"),
        # IPv6, bracketed with a port and bare without one
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("2001:db8::1", "2001:db8::1"),
        # normalised, so one visitor is one bucket
        ("2001:0db8:0000::1", "2001:db8::1"),
        ("::1", "::1"),
        # not addresses
        ("", None),
        ("unknown", None),
        ("localhost:8000", None),
        ("203.0.113.999", None),
        ("203.0.113.5:51234:7", None),
        ("[2001:db8::1", None),
    ],
)
def test_one_forwarded_entry_is_read_as_an_address_or_not_at_all(entry, expected) -> None:
    assert parse_forwarded_entry(entry) == expected


def test_no_trusted_proxy_means_the_header_is_ignored() -> None:
    """The default, and the right answer on a laptop: anyone can send this header."""
    assert forwarded_client_ip("1.2.3.4", 0) is None
    assert forwarded_client_ip("1.2.3.4, 203.0.113.5", 0) is None
    assert forwarded_client_ip("1.2.3.4", -1) is None


def test_one_trusted_proxy_reads_the_right_most_entry() -> None:
    """Azure App Service: one proxy, which appends what it saw."""
    assert forwarded_client_ip("203.0.113.5:51234", 1) == "203.0.113.5"
    # A caller that forged a left-most entry is limited by the real one anyway.
    assert forwarded_client_ip("1.2.3.4, 203.0.113.5:51234", 1) == "203.0.113.5"
    assert forwarded_client_ip("1.2.3.4, 9.9.9.9, 203.0.113.5", 1) == "203.0.113.5"


def test_two_trusted_proxies_count_two_from_the_right() -> None:
    """A CDN in front of the platform: the second-from-last entry is the visitor."""
    header = "1.2.3.4, 203.0.113.5:51234, 10.0.0.7"
    assert forwarded_client_ip(header, 2) == "203.0.113.5"
    assert forwarded_client_ip(header, 3) == "1.2.3.4"


def test_a_header_shorter_than_the_hop_count_falls_back() -> None:
    """Fewer entries than trusted proxies means the request did not come through them."""
    assert forwarded_client_ip("203.0.113.5", 2) is None
    assert forwarded_client_ip("", 1) is None
    assert forwarded_client_ip(None, 1) is None
    assert forwarded_client_ip("   ,  ,  ", 1) is None


def test_a_malformed_entry_falls_back_to_the_peer() -> None:
    """Refusing to guess: an unreadable entry is not an address."""
    assert forwarded_client_ip("1.2.3.4, not-an-ip", 1) is None
    assert forwarded_client_ip("1.2.3.4, 203.0.113.5", 1) == "203.0.113.5"


