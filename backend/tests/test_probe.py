import asyncio
import socket
import ssl

import httpx
import pytest
from httpcore._backends.auto import AutoBackend

from sentinel.probe import Target, probe
from sentinel.security import DestinationBlocked, PublicTransport, public_ip, resolve_public


def target(**values):
    return Target(
        **{
            "id": "test",
            "url": "https://example.com/health",
            "method": "GET",
            "timeout": 2,
            "expected_min": 200,
            "expected_max": 299,
            "latency_threshold": 10000,
            **values,
        }
    )


def response(code=200, **kwargs):
    return httpx.Response(code, stream=httpx.ByteStream(b"ok"), **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [200, 404, 429, 500, 503])
async def test_http_statuses(code):
    result = await probe(target(), transport=httpx.MockTransport(lambda r: response(code)))
    assert result.code == code
    assert result.success is (code == 200)
    assert result.status == ("healthy" if code == 200 else "down")
    assert result.latency_ms >= 0
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_expected_range_and_slow_response():
    result = await probe(
        target(expected_min=400, expected_max=499),
        transport=httpx.MockTransport(lambda r: response(404)),
    )
    assert result.success

    async def slow(request):
        await asyncio.sleep(0.02)
        return response()

    result = await probe(target(latency_threshold=1), transport=httpx.MockTransport(slow))
    assert result.status == "degraded"
    assert result.success  # Valid HTTP availability; latency degradation is separate.
    assert "Latency" in result.error


@pytest.mark.asyncio
async def test_timeout_and_total_deadline():
    async def too_slow(request):
        await asyncio.sleep(1)
        return response()

    result = await probe(target(timeout=0.02), transport=httpx.MockTransport(too_slow))
    assert result.status == "down"
    assert result.code is None
    assert "timed out" in result.error
    assert result.latency_ms < 500


@pytest.mark.asyncio
async def test_safe_retries_and_no_unsafe_replay():
    calls = 0

    async def flaky(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("private driver error must not leak")
        return response()

    result = await probe(target(), transport=httpx.MockTransport(flaky))
    assert result.success and result.attempts == 2
    calls = 0
    result = await probe(target(method="POST"), transport=httpx.MockTransport(flaky))
    assert not result.success and result.attempts == 1 and calls == 0
    assert "Only GET and HEAD" in result.error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "location",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest",
        "file:///etc/passwd",
        "http://example.com/insecure",
    ],
)
async def test_redirect_policy(location):
    calls = 0

    def redirect(request):
        nonlocal calls
        calls += 1
        return response(302, headers={"Location": location})

    result = await probe(target(), transport=httpx.MockTransport(redirect))
    assert result.status == "down"
    assert calls == 1


@pytest.mark.asyncio
async def test_public_redirects_and_limit():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return response(302, headers={"Location": "/ready"})
        return response()

    result = await probe(target(), transport=httpx.MockTransport(handler))
    assert result.success and calls[-1] == "https://example.com/ready"
    result = await probe(
        target(),
        max_redirects=2,
        transport=httpx.MockTransport(lambda r: response(302, headers={"Location": "/loop"})),
    )
    assert not result.success and "redirect" in result.error


@pytest.mark.asyncio
async def test_size_limit_and_compressed_content_is_not_decoded():
    result = await probe(
        target(),
        max_bytes=10,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, stream=httpx.ByteStream(b"x" * 11))
        ),
    )
    assert not result.success and "limit" in result.error
    result = await probe(
        target(),
        max_bytes=10,
        transport=httpx.MockTransport(lambda r: response(headers={"Content-Length": "9000000"})),
    )
    assert not result.success
    # Invalid gzip would fail if the probe tried to decompress it.
    result = await probe(
        target(),
        transport=httpx.MockTransport(lambda r: response(headers={"Content-Encoding": "gzip"})),
    )
    assert result.success


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.1.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
        "ff0e::1",
        "64:ff9b::7f00:1",
        "2002:7f00:1::",
    ],
)
def test_public_address_policy(ip):
    assert not public_ip(ip)


@pytest.mark.asyncio
async def test_mixed_dns_is_rejected(monkeypatch):
    async def mixed(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", mixed)
    with pytest.raises(DestinationBlocked):
        await resolve_public("example.com", 443)


@pytest.mark.asyncio
async def test_dns_failure_is_recorded(monkeypatch):
    async def missing(*args, **kwargs):
        raise socket.gaierror()

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", missing)
    result = await probe(target())
    assert not result.success and "DNS" in result.error and result.attempts == 2


@pytest.mark.asyncio
async def test_numeric_pinning_preserves_host_sni_and_tls_verification(monkeypatch):
    connections, host_headers, sni = [], [], []
    dns_calls = 0

    async def answers(*args, **kwargs):
        nonlocal dns_calls
        dns_calls += 1
        # A second hostname resolution would resolve to loopback.
        ip = "8.8.8.8" if dns_calls == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    class Stream:
        def __init__(self):
            self.sent = False

        async def read(self, max_bytes, timeout=None):
            if self.sent:
                return b""
            self.sent = True
            return b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"

        async def write(self, buffer, timeout=None):
            host_headers.append(buffer)

        async def aclose(self):
            pass

        async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            assert ssl_context.check_hostname and ssl_context.verify_mode == ssl.CERT_REQUIRED
            sni.append(server_hostname)
            return self

        def get_extra_info(self, info):
            return None

    async def connect(self, host, port, *args, **kwargs):
        connections.append(host)
        return Stream()

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", answers)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    result = await probe(target(), transport=PublicTransport())
    assert result.success
    assert connections == ["8.8.8.8"] and dns_calls == 1
    assert sni == ["example.com"]
    assert b"Host: example.com" in b"".join(host_headers)


@pytest.mark.asyncio
async def test_redirect_to_dns_private_host_does_not_connect(monkeypatch):
    connections = []

    async def private(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]

    async def connect(*args, **kwargs):
        connections.append(True)
        raise AssertionError("Never connect to this DNS result")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", private)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    result = await probe(target())
    assert not result.success and "non-public" in result.error
    assert not connections


@pytest.mark.asyncio
async def test_mutating_methods_do_not_follow_redirects():
    calls = []

    def redirect(request):
        calls.append(request.method)
        return response(307, headers={"Location": "https://other.example/path"})

    result = await probe(target(method="DELETE"), transport=httpx.MockTransport(redirect))
    assert calls == [] and result.code is None and not result.success


@pytest.mark.asyncio
async def test_redirect_dns_answer_is_revalidated_before_socket(monkeypatch):
    dns_names, connections = [], []

    async def answers(host, port, **kwargs):
        dns_names.append(host)
        ip = "8.8.8.8" if host == "example.com" else "10.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    class Stream:
        def __init__(self):
            self.sent = False

        async def read(self, max_bytes, timeout=None):
            if self.sent:
                return b""
            self.sent = True
            return b"HTTP/1.1 302 Found\r\nLocation: https://private-answer.example/\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"

        async def write(self, buffer, timeout=None):
            pass

        async def aclose(self):
            pass

        async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            return self

        def get_extra_info(self, info):
            return None

    async def connect(self, host, port, *args, **kwargs):
        connections.append(host)
        return Stream()

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", answers)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    result = await probe(target())
    assert dns_names == ["example.com", "private-answer.example"]
    assert connections == ["8.8.8.8"] and not result.success
    assert "non-public" in result.error
