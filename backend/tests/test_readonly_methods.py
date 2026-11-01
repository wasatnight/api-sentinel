import httpx
import pytest
from pydantic import ValidationError

from sentinel.probe import Target, probe
from sentinel.schemas import ServiceInput


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_input_rejects_unsafe_monitor_methods(method):
    with pytest.raises(ValidationError):
        ServiceInput(name="Fixture", url="https://example.com/health", collection_id="fixture", method=method)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def test_probe_blocks_unsafe_methods_without_transport_call(method):
    def forbidden(request):
        pytest.fail("Unsafe monitor method reached the transport")
    target = Target("fixture", "https://example.com/health", method, 2, 200, 299, 1000)
    result = await probe(target, transport=httpx.MockTransport(forbidden))
    assert not result.success
    assert result.code is None
    assert "Only GET and HEAD" in result.error
