import asyncio
from dataclasses import dataclass
from time import perf_counter
from urllib.parse import urljoin, urlsplit

import httpx

from .security import DestinationBlocked, DNSFailure, PublicTransport, validate_destination


@dataclass(frozen=True)
class Target:
    id: str
    url: str
    method: str
    timeout: int
    expected_min: int
    expected_max: int
    latency_threshold: int


@dataclass(frozen=True)
class Result:
    code: int | None
    latency_ms: float
    success: bool
    status: str
    error: str | None
    attempts: int


class ResponseTooLarge(Exception):
    pass


async def probe(target: Target, *, transport=None, max_bytes=1_048_576, max_redirects=5) -> Result:
    if target.method not in {"GET", "HEAD"}:
        return Result(None, 0.0, False, "down", "Only GET and HEAD monitoring is supported.", 1)
    started = perf_counter()
    attempts = 0
    code = None
    error = None
    status = "down"
    success = False
    # One total deadline covers DNS, all redirects, streaming and a bounded safe retry.
    try:
        async with asyncio.timeout(target.timeout):
            async with httpx.AsyncClient(
                transport=transport or PublicTransport(),
                trust_env=False,
                follow_redirects=False,
                timeout=httpx.Timeout(target.timeout),
                headers={"User-Agent": "API-Sentinel/1.1", "Accept-Encoding": "identity"},
            ) as client:
                max_attempts = 2 if target.method in {"GET", "HEAD"} else 1
                for attempt in range(max_attempts):
                    attempts += 1
                    try:
                        url, method = target.url, target.method
                        for hop in range(max_redirects + 1):
                            validate_destination(url)
                            async with client.stream(method, url) as response:
                                if response.status_code in {301, 302, 303, 307, 308}:
                                    if method not in {"GET", "HEAD"}:
                                        # A check must never replay a mutating method at a redirect target.
                                        code = response.status_code
                                        break
                                    location = response.headers.get("location")
                                    if not location:
                                        code = response.status_code
                                        break
                                    if hop == max_redirects:
                                        raise DestinationBlocked(
                                            "The redirect limit was exceeded."
                                        )
                                    redirect = urljoin(url, location)
                                    validate_destination(redirect)
                                    if (
                                        urlsplit(url).scheme == "https"
                                        and urlsplit(redirect).scheme == "http"
                                    ):
                                        raise DestinationBlocked(
                                            "HTTPS to HTTP redirect blocked."
                                        )
                                    url = redirect
                                    if response.status_code == 303 and method != "HEAD":
                                        method = "GET"
                                    continue
                                code = response.status_code
                                length = response.headers.get("content-length", "")
                                if (
                                    method != "HEAD"
                                    and length.isdigit()
                                    and int(length) > max_bytes
                                ):
                                    raise ResponseTooLarge()
                                size = 0
                                # Count raw bytes; never decompress attacker-controlled response bodies.
                                async for chunk in response.aiter_raw():
                                    size += len(chunk)
                                    if size > max_bytes:
                                        raise ResponseTooLarge()
                                break
                        break
                    except (httpx.ConnectError, httpx.ConnectTimeout, DNSFailure):
                        if attempt + 1 >= max_attempts:
                            raise
                        await asyncio.sleep(0.15)
                success = code is not None and target.expected_min <= code <= target.expected_max
                status = "healthy" if success else "down"
                if not success:
                    error = f"HTTP {code} outside the expected range {target.expected_min}–{target.expected_max}."
    except (TimeoutError, httpx.TimeoutException):
        error = f"Request timed out ({target.timeout} s)."
    except DestinationBlocked as exc:
        error = str(exc)
    except DNSFailure as exc:
        error = str(exc)
    except ResponseTooLarge:
        error = "The response exceeds the 1 MiB limit."
    except httpx.ConnectError:
        error = "Could not establish the connection."
    except httpx.HTTPError:
        error = "HTTP protocol or transport error."
    latency = round((perf_counter() - started) * 1000, 2)
    if success and latency > target.latency_threshold:
        status = "degraded"
        error = f"Latency {latency:.0f} ms exceeds the threshold of {target.latency_threshold} ms."
    return Result(code, latency, success, status, error, attempts)
