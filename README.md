# Free LLM Chat Gateway

A small chat app + HTTP gateway that talks to **many free LLM API providers**,
always uses the **best available model**, and **automatically fails over to the
next provider** when one runs out of its free-tier limit (rate-limit / quota).

You bring the free API keys (see **[docs/GET_API_KEYS.md](docs/GET_API_KEYS.md)**);
the gateway handles routing, failover, cooldowns, and exposes a clean endpoint
plus an OpenAI-compatible API and a tiny browser chat UI.

```
                         ┌───────────────────────────────────────┐
  POST /chat ───────────▶│  Router: best model first, fail over   │
  POST /v1/chat/...      │  on 429 / quota, cooldown & skip        │
  Browser UI  /          └───────────────────────────────────────┘
                            │      │      │      │      │
                          Gemini Cerebras Groq SambaNova … (OpenAI-compatible)
```

## Why it works this way

Almost every usable free LLM API in 2026 (Google Gemini, Groq, Cerebras,
SambaNova, NVIDIA NIM, Mistral, OpenRouter, GitHub Models, Cohere, Cloudflare)
speaks the **OpenAI Chat Completions protocol**. So each provider is just a
`base_url` + key + model list. The router flattens every model into one
priority-ordered list (best quality first, fastest hardware as tiebreaker) and
walks it until one succeeds.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # add at least one provider key (see the docs)
uvicorn app.main:app --reload
```

Then open <http://localhost:8000> to chat in the browser.

> You only need **one** key to start. The gateway skips any provider whose key
> is missing — check `GET /providers` to see what's live.

## API

### `POST /chat` — the friendly endpoint
```bash
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message": "Explain failover in one sentence."}'
```
```json
{
  "content": "Failover automatically reroutes a request to the next available provider when the current one fails or is rate-limited.",
  "provider": "gemini",
  "model": "gemini-2.5-pro",
  "latency_ms": 742,
  "attempts": ["gemini/gemini-2.5-pro"],
  "usage": { "prompt_tokens": 14, "completion_tokens": 21, "total_tokens": 35 }
}
```

Multi-turn — send the whole history:
```json
{ "messages": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello!"},
    {"role": "user", "content": "What did I just say?"}
] }
```

Optional fields: `system`, `temperature`, `max_tokens`, and `model`
(`"auto"` for best-available, or a specific id like `"llama-3.3-70b-versatile"`
to pin one).

### `POST /chat/stream` — Server-Sent Events
Streams `route`, `delta`, and `done`/`error` events. Used by the web UI.

### `POST /v1/chat/completions` — OpenAI-compatible
Point the official OpenAI SDK at the gateway and it just works (streaming too):
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused")
r = client.chat.completions.create(
    model="auto",                      # or pin a model id
    messages=[{"role": "user", "content": "hello"}],
)
print(r.choices[0].message.content)
```

### `GET /providers` — live status
Shows each provider: `enabled`, models, `cooldown_seconds_left`, success/failure
counts, and why a provider is disabled (e.g. missing key).

### `GET /healthz`
Liveness + list of enabled providers.

## How failover works

- Routes are tried **best-first** (`quality` score, then provider `speed`).
- On **HTTP 429 / quota**, the provider is put on a **cooldown** (honoring a
  `Retry-After` header if sent) and skipped until it expires — so the next
  request lands on the next-best model automatically.
- On an **auth error (401)**, the provider is disabled for the process (bad key).
- On **connection/5xx errors**, a short cooldown, then the next route is tried.
- If every eligible route fails, `/chat` returns **503** with the list of
  attempts.

For streaming, failover happens up to the first streamed byte; once a provider
starts emitting tokens we commit to it.

## Configuration

All via env / `.env` (see `.env.example`):

| Var | Default | Meaning |
|---|---|---|
| `GATEWAY_API_KEY` | _(none)_ | If set, clients must send it as `Authorization: Bearer …` or `x-api-key`. |
| `LLM_DEFAULT_COOLDOWN` | `60` | Seconds to rest a provider after a 429 with no `Retry-After`. |
| `LLM_TRANSIENT_COOLDOWN` | `15` | Seconds to rest after a connection/5xx error. |
| `LLM_REQUEST_TIMEOUT` | `60` | Per-attempt timeout (seconds). |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address. |

Plus one key var per provider — see **[docs/GET_API_KEYS.md](docs/GET_API_KEYS.md)**.

## Adding or re-prioritizing providers/models

Everything lives in **`app/providers.py`**. Append a `Provider`, or change a
model's `quality` number to move it up/down the priority list. No other code
changes needed.

## Tests

```bash
pip install -r requirements.txt
pytest
```

The tests exercise the router's failover, cooldown, auth-disable, model-pinning,
and exhaustion paths with **fake clients — no real keys or network required**.

## Project layout

```
app/
  providers.py   # provider + model registry (edit this to add providers)
  router.py      # the failover engine
  main.py        # FastAPI endpoints
  schemas.py     # request/response models
  config.py      # env-driven settings
static/index.html  # browser chat UI
docs/GET_API_KEYS.md  # how to obtain each free key
tests/test_router.py  # failover tests (no network)
```
