"""
Registry of free LLM API providers and their models.

Almost every usable free LLM API in 2026 speaks the OpenAI Chat Completions
protocol (``POST {base_url}/chat/completions`` with a Bearer key), so we model
every provider the same way: a base URL, the env var that holds its key, and a
list of models with a quality score. The router (``app/router.py``) flattens all
models into one priority-ordered list and walks it, skipping providers that have
no key or are temporarily rate-limited.

To add a provider: append a ``Provider`` below. To change which model is
preferred: tweak the ``quality`` numbers. No other code needs to change.

Quality scale (rough, free-tier-relevant):
    100  frontier (Gemini 2.5 Pro, DeepSeek R1/V3, Llama 405B)
     85  strong  (Llama 3.3 70B, Qwen 72B, Mistral Large, Gemini 2.5 Flash)
     60  small   (Llama 3.1 8B, Mistral small, Gemini Flash-Lite)
     40  tiny    (Llama 3.2 3B and friends)

``speed`` is a tiebreaker between equal-quality routes (higher = faster
inference hardware). Cerebras/Groq win here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Model:
    """A single model offered by a provider."""

    id: str          # the model id sent to the API
    quality: int     # see scale above
    label: str = ""  # human-friendly name for /providers


@dataclass
class Provider:
    """A free, OpenAI-compatible LLM API provider."""

    name: str
    base_url: str
    api_key_env: str
    models: list[Model]
    speed: int = 50                 # tiebreaker for equal-quality models
    default_cooldown: float = 60.0  # seconds to rest a provider after a 429
    # Optional second env var some providers need woven into the base_url
    # (e.g. Cloudflare account id). Rendered with str.format(**os.environ).
    requires_env: tuple[str, ...] = field(default_factory=tuple)
    docs: str = ""
    # True only for standing free tiers (no card, no expiry). False for
    # trial-credit or prepaid-billing providers — see `free_note`.
    permanent_free: bool = True
    free_note: str = ""

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)

    @property
    def resolved_base_url(self) -> Optional[str]:
        """base_url with any ``{ENV_VAR}`` placeholders filled in, or None if
        a required env var is missing."""
        try:
            return self.base_url.format(**os.environ)
        except KeyError:
            return None

    @property
    def enabled(self) -> bool:
        """True when every credential this provider needs is present."""
        if not self.api_key:
            return False
        if self.resolved_base_url is None:
            return False
        return all(os.environ.get(var) for var in self.requires_env)


# ---------------------------------------------------------------------------
# The registry. All of these have a genuine, no-credit-card free tier in 2026.
# ---------------------------------------------------------------------------
PROVIDERS: list[Provider] = [
    # ----- Standing free tiers: no card, no expiry (preferred defaults) -----
    Provider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        speed=95,  # very fast (~300+ tok/s)
        docs="https://console.groq.com/keys",
        free_note="Permanent free, no card. ~14,400 req/day, 30k tok/min per model.",
        models=[
            Model("openai/gpt-oss-120b", 88, "GPT-OSS 120B (Groq)"),
            Model("llama-3.3-70b-versatile", 85, "Llama 3.3 70B (Groq)"),
            Model("llama-3.1-8b-instant", 60, "Llama 3.1 8B (Groq)"),
        ],
    ),
    Provider(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        api_key_env="CEREBRAS_API_KEY",
        speed=100,  # fastest inference available on a free tier (~2000 tok/s)
        docs="https://cloud.cerebras.ai",
        free_note="Permanent free, no card. ~1M tokens/day; 8k-token context cap on free tier.",
        models=[
            # Cerebras retired its Llama free models in 2026; these are what the
            # free tier actually serves now (see GET /v1/models).
            Model("gpt-oss-120b", 88, "GPT-OSS 120B (Cerebras)"),
            Model("zai-glm-4.7", 85, "GLM 4.7 (Cerebras)"),
        ],
    ),
    Provider(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        speed=55,
        docs="https://openrouter.ai/keys",
        free_note="`:free` models, no card. ~50 req/day (rises to 1,000/day after a one-time $10 top-up).",
        models=[
            # ``:free`` variants are permanently free on OpenRouter. DeepSeek R1
            # and Mistral Small ``:free`` were discontinued in 2026; these are
            # current free ids (the free pool is often upstream-rate-limited).
            Model("nousresearch/hermes-3-llama-3.1-405b:free", 88, "Hermes 3 405B (OpenRouter)"),
            Model("meta-llama/llama-3.3-70b-instruct:free", 85, "Llama 3.3 70B (OpenRouter)"),
            Model("qwen/qwen3-next-80b-a3b-instruct:free", 80, "Qwen3 Next 80B (OpenRouter)"),
        ],
    ),
    Provider(
        name="github",
        base_url="https://models.github.ai/inference",
        api_key_env="GITHUB_MODELS_TOKEN",
        speed=55,
        docs="https://github.com/marketplace/models",
        free_note="Free for any GitHub account (PAT with models:read). Per-minute/day caps.",
        models=[
            Model("openai/gpt-4.1", 90, "GPT-4.1 (GitHub Models)"),
            # Catalog id is lowercase; the mixed-case form 404s.
            Model("meta/llama-3.3-70b-instruct", 85, "Llama 3.3 70B (GitHub Models)"),
            Model("openai/gpt-4.1-mini", 70, "GPT-4.1 mini (GitHub Models)"),
        ],
    ),
    Provider(
        name="cloudflare",
        base_url="https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
        api_key_env="CLOUDFLARE_API_TOKEN",
        requires_env=("CLOUDFLARE_ACCOUNT_ID",),
        speed=60,
        docs="https://dash.cloudflare.com/?to=/:account/ai/workers-ai",
        free_note="Permanent free, no card. ~10k neurons/day. Needs account id too.",
        models=[
            Model("@cf/meta/llama-3.3-70b-instruct-fp8-fast", 85, "Llama 3.3 70B (Cloudflare)"),
            # @cf/meta/llama-3.1-8b-instruct was retired (HTTP 410); fp8 is current.
            Model("@cf/meta/llama-3.1-8b-instruct-fp8", 60, "Llama 3.1 8B (Cloudflare)"),
        ],
    ),
    Provider(
        name="sambanova",
        base_url="https://api.sambanova.ai/v1",
        api_key_env="SAMBANOVA_API_KEY",
        speed=85,
        docs="https://cloud.sambanova.ai/apis",
        free_note="Permanent free tier (~20 RPM, 200k tok/day), no card. Plus $5 expiring bonus credits.",
        models=[
            Model("DeepSeek-R1", 95, "DeepSeek R1 (SambaNova)"),
            Model("Meta-Llama-3.3-70B-Instruct", 85, "Llama 3.3 70B (SambaNova)"),
            Model("Meta-Llama-3.1-8B-Instruct", 60, "Llama 3.1 8B (SambaNova)"),
        ],
    ),
    Provider(
        name="mistral",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        speed=65,
        docs="https://console.mistral.ai/api-keys",
        free_note="Permanent free 'Experiment' tier (~1B tok/mo), no card — but requires opting into data training.",
        models=[
            Model("mistral-large-latest", 85, "Mistral Large"),
            Model("mistral-small-latest", 60, "Mistral Small"),
        ],
    ),
    # ----- NOT a standing free tier: trial credits / prepaid / restricted ----
    # These are kept so you can still use them if you have credits/entitlement,
    # but they are deprioritized and clearly flagged in /providers and the docs.
    Provider(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GEMINI_API_KEY",
        speed=70,
        docs="https://aistudio.google.com/apikey",
        permanent_free=False,
        free_note="New AI Studio accounts now require PREPAID billing (since Mar 2026); "
        "Pro went paid in Apr 2026. Only existing accounts still get Flash free.",
        models=[
            # gemini-2.5-pro removed: it is no longer on the free tier.
            Model("gemini-2.5-flash", 85, "Gemini 2.5 Flash"),
            Model("gemini-2.5-flash-lite", 60, "Gemini 2.5 Flash-Lite"),
        ],
    ),
    Provider(
        name="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env="NVIDIA_API_KEY",
        speed=60,
        docs="https://build.nvidia.com",
        permanent_free=False,
        free_note="Trial credits that EXPIRE (~30 days / 5,000 credits), not a standing free tier.",
        models=[
            Model("deepseek-ai/deepseek-r1", 95, "DeepSeek R1 (NVIDIA)"),
            Model("meta/llama-3.3-70b-instruct", 85, "Llama 3.3 70B (NVIDIA)"),
            Model("meta/llama-3.1-8b-instruct", 60, "Llama 3.1 8B (NVIDIA)"),
        ],
    ),
    Provider(
        name="cohere",
        base_url="https://api.cohere.ai/compatibility/v1",
        api_key_env="COHERE_API_KEY",
        speed=55,
        docs="https://dashboard.cohere.com/api-keys",
        permanent_free=False,
        free_note="Trial key: 1,000 calls/month (resets), no card — but NOT allowed for production/commercial use.",
        models=[
            Model("command-a-03-2025", 80, "Command A (Cohere)"),
            Model("command-r-plus", 70, "Command R+ (Cohere)"),
        ],
    ),
]


PROVIDERS_BY_NAME: dict[str, Provider] = {p.name: p for p in PROVIDERS}


@dataclass(frozen=True)
class Route:
    """A (provider, model) pair — one attemptable destination for a request."""

    provider: Provider
    model: Model

    @property
    def id(self) -> str:
        return f"{self.provider.name}/{self.model.id}"

    # Sort key: best quality first, then prefer truly-free providers over
    # trial/prepaid ones, then fastest hardware. Stable, deterministic order.
    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (
            -self.model.quality,
            0 if self.provider.permanent_free else 1,
            -self.provider.speed,
        )


def all_routes() -> list[Route]:
    """Every (provider, model) route, priority-ordered (best first)."""
    routes = [
        Route(provider, model)
        for provider in PROVIDERS
        for model in provider.models
    ]
    routes.sort(key=lambda r: r.sort_key)
    return routes


def enabled_routes() -> list[Route]:
    """Priority-ordered routes whose provider has all required credentials."""
    return [r for r in all_routes() if r.provider.enabled]
