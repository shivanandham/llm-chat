"""Runtime configuration, loaded from environment / .env."""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load .env from the repo root if present. Real env vars win over .env.
load_dotenv()


class Settings:
    # Per-attempt HTTP timeout when calling a provider.
    request_timeout: float = float(os.environ.get("LLM_REQUEST_TIMEOUT", "60"))
    # Cooldown (seconds) applied to a provider after a rate-limit, when the
    # provider does not send a Retry-After header.
    default_cooldown: float = float(os.environ.get("LLM_DEFAULT_COOLDOWN", "60"))
    # Cooldown after a transient/connection/5xx error.
    transient_cooldown: float = float(os.environ.get("LLM_TRANSIENT_COOLDOWN", "15"))
    # Optional API key clients must send as `Authorization: Bearer <key>` /
    # `x-api-key`. If unset, the gateway is open (fine for localhost).
    gateway_api_key: str | None = os.environ.get("GATEWAY_API_KEY") or None
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", "8000"))


settings = Settings()
