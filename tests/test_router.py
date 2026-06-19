"""
Failover tests for the Router — no real API keys or network needed.

We enable a couple of providers via env vars, then swap their OpenAI clients for
fakes that raise/return what we want, and assert the router walks the priority
list and fails over correctly.
"""

import time

import httpx
import openai
import pytest

import app.router as router_mod
from app.providers import PROVIDERS_BY_NAME
from app.router import AllProvidersExhausted, Router


# --- fakes -----------------------------------------------------------------
class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]
        self.usage = None


class FakeClient:
    """Stands in for AsyncOpenAI. `behavior(model)` returns content or raises."""

    def __init__(self, behavior):
        self._behavior = behavior
        outer = self

        class _Completions:
            async def create(self, model, messages, **kwargs):
                return outer._behavior(model)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _rate_limit_error():
    req = httpx.Request("POST", "https://example/chat/completions")
    resp = httpx.Response(429, headers={"retry-after": "30"}, request=req)
    return openai.RateLimitError("rate limited", response=resp, body=None)


@pytest.fixture
def two_providers(monkeypatch):
    """Enable exactly gemini (quality 100) and groq, give known API keys."""
    for name in PROVIDERS_BY_NAME:
        monkeypatch.delenv(PROVIDERS_BY_NAME[name].api_key_env, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")


def _wire(router: Router, behaviors: dict):
    """Make router._client(provider) return a FakeClient per provider name."""
    clients = {name: FakeClient(beh) for name, beh in behaviors.items()}
    router._client = lambda provider: clients[provider.name]  # type: ignore


# --- tests -----------------------------------------------------------------
@pytest.mark.asyncio
async def test_picks_best_provider_first(two_providers):
    r = Router()
    _wire(r, {
        "gemini": lambda m: _Resp("hi from gemini"),
        "groq": lambda m: _Resp("hi from groq"),
    })
    out = await r.complete([{"role": "user", "content": "hello"}])
    # Gemini 2.5 Pro has the highest quality score, so it must be tried first.
    assert out.provider == "gemini"
    assert out.content == "hi from gemini"
    assert out.attempts[0].startswith("gemini/")


@pytest.mark.asyncio
async def test_fails_over_on_rate_limit(two_providers):
    r = Router()

    def gemini_behavior(model):
        raise _rate_limit_error()

    _wire(r, {
        "gemini": gemini_behavior,
        "groq": lambda m: _Resp("groq saves the day"),
    })
    out = await r.complete([{"role": "user", "content": "hello"}])
    assert out.provider == "groq"
    assert out.content == "groq saves the day"
    # Gemini should now be cooling down (retry-after: 30).
    gemini = PROVIDERS_BY_NAME["gemini"]
    assert r.state(gemini).cooldown_left(time.time()) > 0
    assert any(a.startswith("gemini/") for a in out.attempts)


@pytest.mark.asyncio
async def test_cooldown_skips_provider(two_providers):
    r = Router()
    gemini = PROVIDERS_BY_NAME["gemini"]
    r.state(gemini).cooldown_until = time.time() + 999  # force cooldown
    _wire(r, {
        "gemini": lambda m: _Resp("should be skipped"),
        "groq": lambda m: _Resp("groq used"),
    })
    out = await r.complete([{"role": "user", "content": "hi"}])
    assert out.provider == "groq"
    assert not any(a.startswith("gemini/") for a in out.attempts)


@pytest.mark.asyncio
async def test_auth_error_disables_provider(two_providers):
    r = Router()
    req = httpx.Request("POST", "https://example/chat/completions")
    auth_err = openai.AuthenticationError(
        "bad key", response=httpx.Response(401, request=req), body=None
    )

    def gemini_behavior(model):
        raise auth_err

    _wire(r, {
        "gemini": gemini_behavior,
        "groq": lambda m: _Resp("ok"),
    })
    await r.complete([{"role": "user", "content": "hi"}])
    assert r.state(PROVIDERS_BY_NAME["gemini"]).disabled_reason is not None


@pytest.mark.asyncio
async def test_all_exhausted_raises(two_providers):
    r = Router()

    def boom(model):
        raise _rate_limit_error()

    _wire(r, {"gemini": boom, "groq": boom})
    with pytest.raises(AllProvidersExhausted) as exc:
        await r.complete([{"role": "user", "content": "hi"}])
    assert len(exc.value.attempts) >= 2


@pytest.mark.asyncio
async def test_pin_specific_model(two_providers):
    r = Router()
    _wire(r, {
        "gemini": lambda m: _Resp("gemini"),
        "groq": lambda m: _Resp(f"groq:{m}"),
    })
    out = await r.complete(
        [{"role": "user", "content": "hi"}], model="llama-3.1-8b-instant"
    )
    assert out.provider == "groq"
    assert out.model == "llama-3.1-8b-instant"


class FakeStreamClient:
    """Stands in for AsyncOpenAI when stream=True: create() returns an async
    iterator of chunk objects, or raises before iteration starts."""

    def __init__(self, deltas=None, raises=None):
        outer = self

        class _Delta:
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, content):
                self.delta = _Delta(content)

        class _Chunk:
            def __init__(self, content):
                self.choices = [_Choice(content)]

        class _Stream:
            def __aiter__(self):
                self._it = iter(deltas or [])
                return self

            async def __anext__(self):
                try:
                    return _Chunk(next(self._it))
                except StopIteration:
                    raise StopAsyncIteration

        class _Completions:
            async def create(self, model, messages, stream=False, **kwargs):
                if raises is not None:
                    raise raises
                return _Stream()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


@pytest.mark.asyncio
async def test_stream_fails_over_then_streams(two_providers):
    r = Router()
    clients = {
        "gemini": FakeStreamClient(raises=_rate_limit_error()),
        "groq": FakeStreamClient(deltas=["Hel", "lo", "!"]),
    }
    r._client = lambda provider: clients[provider.name]  # type: ignore

    chunks = []
    chosen = None
    async for route, delta in r.stream([{"role": "user", "content": "hi"}]):
        chosen = route
        chunks.append(delta)
    assert chosen.provider.name == "groq"
    assert "".join(chunks) == "Hello!"


@pytest.mark.asyncio
async def test_no_providers_configured(monkeypatch):
    for p in PROVIDERS_BY_NAME.values():
        monkeypatch.delenv(p.api_key_env, raising=False)
    r = Router()
    with pytest.raises(AllProvidersExhausted):
        await r.complete([{"role": "user", "content": "hi"}])
