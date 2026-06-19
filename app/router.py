"""
The failover engine.

`Router.complete()` walks the priority-ordered list of (provider, model) routes
and returns the first successful completion. When a provider is rate-limited
(HTTP 429) or out of quota it is put on a cooldown and skipped until the
cooldown expires, so the next request transparently lands on the next-best
model. Auth failures disable a provider for the process lifetime.

All providers here are OpenAI-compatible, so a single `AsyncOpenAI` client per
provider (just a different base_url + key) is all we need.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import openai
from openai import AsyncOpenAI

from .config import settings
from .providers import Provider, Route, enabled_routes

log = logging.getLogger("llm-chat.router")


class AllProvidersExhausted(Exception):
    """Raised when every eligible route failed for a single request."""

    def __init__(self, attempts: list[str], last_error: Optional[str]):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"All providers exhausted after {len(attempts)} attempt(s). "
            f"Last error: {last_error}"
        )


@dataclass
class ProviderState:
    """Mutable per-provider health, tracked across requests."""

    cooldown_until: float = 0.0
    disabled_reason: Optional[str] = None  # set on auth failure -> skip for good
    successes: int = 0
    failures: int = 0

    def cooling(self, now: float) -> bool:
        return now < self.cooldown_until

    def cooldown_left(self, now: float) -> int:
        return max(0, int(self.cooldown_until - now))


@dataclass
class Completion:
    content: str
    provider: str
    model: str
    latency_ms: int
    attempts: list[str] = field(default_factory=list)
    usage: Optional[dict] = None


class Router:
    def __init__(self) -> None:
        self._states: dict[str, ProviderState] = {}
        self._clients: dict[str, AsyncOpenAI] = {}

    # -- provider health -----------------------------------------------------
    def state(self, provider: Provider) -> ProviderState:
        return self._states.setdefault(provider.name, ProviderState())

    def _client(self, provider: Provider) -> AsyncOpenAI:
        if provider.name not in self._clients:
            self._clients[provider.name] = AsyncOpenAI(
                api_key=provider.api_key,
                base_url=provider.resolved_base_url,
                timeout=settings.request_timeout,
                max_retries=0,  # we handle retries/failover ourselves
            )
        return self._clients[provider.name]

    def _routes(self, model: str) -> list[Route]:
        """Eligible routes. `auto` -> all enabled, best-first. Otherwise only
        routes whose model id matches `model` (lets callers pin a model)."""
        routes = enabled_routes()
        if model and model != "auto":
            routes = [r for r in routes if r.model.id == model]
        return routes

    # -- cooldown bookkeeping ------------------------------------------------
    def _trip_cooldown(self, provider: Provider, seconds: float) -> None:
        self.state(provider).cooldown_until = time.time() + seconds

    @staticmethod
    def _retry_after(err: openai.APIStatusError, fallback: float) -> float:
        """Honour a Retry-After header if the provider sent one."""
        try:
            header = err.response.headers.get("retry-after")
            if header:
                return float(header)
        except Exception:  # noqa: BLE001 - header parsing is best-effort
            pass
        return fallback

    # -- the main entry points ----------------------------------------------
    async def complete(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Completion:
        routes = self._routes(model)
        if not routes:
            raise AllProvidersExhausted(
                attempts=[],
                last_error=(
                    "No eligible providers. Set at least one provider API key "
                    "(see docs/GET_API_KEYS.md), or `model` matched nothing."
                ),
            )

        now = time.time()
        attempts: list[str] = []
        last_error: Optional[str] = None
        kwargs = _call_kwargs(temperature, max_tokens)

        for route in routes:
            provider, state = route.provider, self.state(route.provider)
            if state.disabled_reason or state.cooling(now):
                continue

            attempts.append(route.id)
            start = time.time()
            try:
                resp = await self._client(provider).chat.completions.create(
                    model=route.model.id, messages=messages, **kwargs
                )
                state.successes += 1
                return Completion(
                    content=resp.choices[0].message.content or "",
                    provider=provider.name,
                    model=route.model.id,
                    latency_ms=int((time.time() - start) * 1000),
                    attempts=attempts,
                    usage=resp.usage.model_dump() if resp.usage else None,
                )
            except Exception as err:  # noqa: BLE001 - normalised below
                last_error = self._handle_error(provider, route, err)

        raise AllProvidersExhausted(attempts, last_error)

    async def stream(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[tuple[Route, str]]:
        """Yield (route, text_delta) chunks from the first route that connects.

        Note: failover happens only until the first byte. Once a provider has
        started streaming we commit to it (we can't un-send partial output).
        """
        routes = self._routes(model)
        if not routes:
            raise AllProvidersExhausted(
                attempts=[], last_error="No eligible providers configured."
            )

        now = time.time()
        last_error: Optional[str] = None
        kwargs = _call_kwargs(temperature, max_tokens)

        for route in routes:
            provider, state = route.provider, self.state(route.provider)
            if state.disabled_reason or state.cooling(now):
                continue
            try:
                stream = await self._client(provider).chat.completions.create(
                    model=route.model.id, messages=messages, stream=True, **kwargs
                )
                started = False
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        started = True
                        yield route, delta
                if started:
                    state.successes += 1
                    return
            except Exception as err:  # noqa: BLE001
                last_error = self._handle_error(provider, route, err)

        raise AllProvidersExhausted([], last_error)

    # -- error normalisation -------------------------------------------------
    def _handle_error(self, provider: Provider, route: Route, err: Exception) -> str:
        """Update provider health based on the failure and return a message."""
        state = self.state(provider)
        state.failures += 1

        if isinstance(err, openai.RateLimitError):
            wait = self._retry_after(err, settings.default_cooldown)
            self._trip_cooldown(provider, wait)
            msg = f"{route.id}: rate-limited, cooling down {int(wait)}s"
        elif isinstance(err, openai.AuthenticationError):
            state.disabled_reason = "authentication failed (bad/expired key)"
            msg = f"{route.id}: auth failed, disabling provider"
        elif isinstance(err, openai.PermissionDeniedError):
            # 403 — often quota/billing or model-not-entitled. Rest it a while.
            self._trip_cooldown(provider, settings.default_cooldown)
            msg = f"{route.id}: permission denied / quota, cooling down"
        elif isinstance(err, openai.APIStatusError):
            status = getattr(err, "status_code", 0)
            if status in (402, 429):
                wait = self._retry_after(err, settings.default_cooldown)
                self._trip_cooldown(provider, wait)
                msg = f"{route.id}: HTTP {status}, cooling down {int(wait)}s"
            else:
                self._trip_cooldown(provider, settings.transient_cooldown)
                msg = f"{route.id}: HTTP {status}"
        else:
            # Connection errors, timeouts, unexpected bugs: brief cooldown.
            self._trip_cooldown(provider, settings.transient_cooldown)
            msg = f"{route.id}: {type(err).__name__}: {err}"

        log.warning(msg)
        return msg


# Module-level singleton used by the API.
router = Router()


def _call_kwargs(temperature: Optional[float], max_tokens: Optional[int]) -> dict:
    kwargs: dict = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return kwargs
