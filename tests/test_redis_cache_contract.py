"""In-process cache contracts with synthetic Redis clients; no live Redis proof."""

import asyncio
import importlib
import inspect
import json
from unittest.mock import Mock

import pytest
import redis

cache_module = importlib.import_module("lexecon.cache.redis_cache")


def test_client_factory_is_not_globally_faked():
    assert not isinstance(cache_module.redis.from_url, Mock)
    assert cache_module._cache_instance is None


@pytest.fixture
def fake_redis(monkeypatch):
    """Only implement the Redis client operations exercised by this contract."""
    values = {}
    client = Mock(spec=redis.Redis)
    client.ping.return_value = True
    client.get.side_effect = values.get

    def setex(key, seconds, value):
        assert isinstance(seconds, int)
        assert seconds > 0
        assert isinstance(value, str)
        values[key] = value
        return True

    client.setex.side_effect = setex
    monkeypatch.setattr(cache_module.redis, "from_url", Mock(return_value=client))
    monkeypatch.setattr(cache_module, "_cache_instance", None)
    return client


def test_async_cache_stores_awaited_result_and_hits(fake_redis):
    calls = []

    @cache_module.redis_cache("async-contract", ttl=17)
    async def compute(value):
        calls.append(value)
        return {"value": value}

    async def scenario():
        assert await compute(4) == {"value": 4}
        assert await compute(4) == {"value": 4}
        assert await compute(5) == {"value": 5}

    assert inspect.iscoroutinefunction(compute)
    asyncio.run(scenario())
    assert calls == [4, 5]
    fake_redis.ping.assert_called_once_with()
    assert fake_redis.setex.call_count == 2
    assert all(call.args[1] == 17 for call in fake_redis.setex.call_args_list)
    assert [json.loads(call.args[2]) for call in fake_redis.setex.call_args_list] == [{"value": 4}, {"value": 5}]


def test_sync_cache_remains_synchronous_and_hits(fake_redis):
    calls = []

    @cache_module.redis_cache("sync-contract", ttl=19)
    def compute(value):
        calls.append(value)
        return {"value": value}

    assert not inspect.iscoroutinefunction(compute)
    assert compute(3) == compute(3) == {"value": 3}
    assert calls == [3]
    fake_redis.setex.assert_called_once()


def test_unavailable_cache_preserves_async_handler(redis_unavailable):
    calls = []

    @cache_module.redis_cache("unavailable")
    async def compute():
        calls.append(True)
        return {"ok": True}

    async def scenario():
        assert await compute() == {"ok": True}
        assert await compute() == {"ok": True}

    assert inspect.iscoroutinefunction(compute)
    asyncio.run(scenario())
    assert len(calls) == 2
    redis_unavailable.ping.assert_called_once_with()
    redis_unavailable.get.assert_not_called()
    redis_unavailable.setex.assert_not_called()


def test_unavailable_cache_preserves_sync_handler(redis_unavailable):
    @cache_module.redis_cache("unavailable-sync")
    def compute():
        return {"ok": True}

    assert compute() == {"ok": True}
    redis_unavailable.ping.assert_called_once_with()
    redis_unavailable.get.assert_not_called()


@pytest.mark.parametrize("operation", ["get", "setex"])
def test_redis_operation_errors_preserve_async_result(fake_redis, operation):
    getattr(fake_redis, operation).side_effect = redis.ConnectionError("synthetic disconnected cache")

    @cache_module.redis_cache("disconnected")
    async def compute():
        return {"ok": True}

    assert asyncio.run(compute()) == {"ok": True}


def test_handler_failure_is_not_cached(fake_redis):
    @cache_module.redis_cache("handler-error")
    async def compute():
        raise ValueError("synthetic handler error")

    with pytest.raises(ValueError, match="synthetic handler error"):
        asyncio.run(compute())
    fake_redis.setex.assert_not_called()


def test_guard_error_is_not_converted_to_cache_fallback(fake_redis):
    fake_redis.ping.side_effect = RuntimeError("synthetic offline guard refusal")
    with pytest.raises(RuntimeError, match="synthetic offline guard refusal"):
        cache_module.get_redis_cache()
    assert cache_module._cache_instance is None


@pytest.mark.parametrize("path", ["/status", "/api/governance/compliance/statistics"])
def test_routes_use_awaited_json_on_fake_cache_hits(authenticated_client, fake_redis, path):
    first = authenticated_client.get(path)
    second = authenticated_client.get(path)
    assert first.status_code == second.status_code == 200
    assert isinstance(first.json(), dict)
    assert second.json() == first.json()
    fake_redis.ping.assert_called_once_with()
    fake_redis.setex.assert_called_once()


def test_fake_cache_does_not_bypass_session_check(authenticated_client, fake_redis):
    path = "/api/governance/compliance/statistics"
    assert authenticated_client.get(path).status_code == 200
    cached_reads = fake_redis.get.call_count
    assert authenticated_client.get(path, headers={"Authorization": "Bearer synthetic-invalid"}).status_code == 401
    assert fake_redis.get.call_count == cached_reads
