import pytest

from app.yuanta import YuantaNotConfigured, fetch_yuanta_quote


@pytest.mark.asyncio
async def test_yuanta_requires_gateway(monkeypatch):
    monkeypatch.delenv("YUANTA_GATEWAY_URL", raising=False)
    with pytest.raises(YuantaNotConfigured):
        await fetch_yuanta_quote("2330", "台積電")
