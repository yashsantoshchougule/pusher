import httpx
import pytest

from backend.core import target_service


@pytest.mark.asyncio
@pytest.mark.parametrize("code, message", [
    (200, "one HEAD request"),
    (403, "refused"),
    (429, "rate limited"),
    (405, "does not support HEAD"),
    (501, "HEAD is not implemented"),
    (None, "before receiving an HTTP response"),
])
async def test_edge_probe_reports_only_observed_outcome(monkeypatch, code, message):
    url = "https://example.invalid/orders"
    monkeypatch.setattr(target_service, "verified_destination", lambda value, _: httpx.URL(value))
    calls = []

    def respond(request):
        calls.append(request)
        assert request.method == "HEAD" and str(request.url) == url
        assert "authorization" not in request.headers
        assert not any(name.startswith("x-pusher-") for name in request.headers)
        if code is None:
            raise httpx.ConnectError("test connection failure", request=request)
        return httpx.Response(code, headers={"cf-ray": "synthetic"})

    monkeypatch.setattr(target_service, "target_client", lambda *a, **kw:
                        httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    result = await target_service.probe_edge(url + "?key=synthetic-private")
    assert len(calls) == 1
    assert result["probe_endpoint"] == url
    assert result["simulated"] is False and result["status_code"] == code
    assert result["edge_hint"] == ("Cloudflare" if code is not None else None)
    assert message in result["recommendation"]

    simulation = await target_service.probe_edge(url, is_sandbox=True)
    assert len(calls) == 1
    assert simulation["simulated"] and simulation["latency_ms"] is None
