# How to collect free LLM API keys

This gateway works with any number of providers — **even one key is enough to
start**. Add more to get more total free capacity and longer uptime before
everything is rate-limited at once.

All providers below have a **genuine free tier in 2026** and (with the
exception noted) require **no credit card**. Every one speaks the OpenAI Chat
Completions protocol, which is why the gateway can treat them uniformly.

After you collect keys, put them in a `.env` file in the repo root (copy
`.env.example`). The env var name for each provider is listed below and in
`app/providers.py`.

---

## Quick-start: the 3 highest-value keys

If you only do three, do these — they cover quality, speed, and breadth:

| Provider | Why | Free tier (approx, 2026) | Card? |
|---|---|---|---|
| **Google Gemini** | Best free-tier quality (Gemini 2.5 Pro/Flash), huge context | ~1,000–1,500 req/day, up to 1M-token context | No |
| **Groq** | Extremely fast (~300+ tok/s), Llama 3.3 70B | ~30 req/min, generous daily token budget | No |
| **Cerebras** | Fastest inference anywhere (~2,000 tok/s) | Free dev tier, per-minute + daily caps | No |

---

## Provider-by-provider

### 1. Google Gemini (Google AI Studio) — `GEMINI_API_KEY`
1. Go to <https://aistudio.google.com/apikey>.
2. Sign in with a Google account.
3. Click **Create API key** → copy it.
4. Set `GEMINI_API_KEY=...` in `.env`.
- **Free tier:** ~5–15 RPM and ~100–1,000 requests/day depending on model
  (Pro is the tightest, Flash-Lite the loosest), up to 1M-token context. No card.

### 2. Cerebras — `CEREBRAS_API_KEY`
1. Go to <https://cloud.cerebras.ai> and sign up (Google/GitHub/email).
2. Open **API Keys** → **Create API Key** → copy.
3. Set `CEREBRAS_API_KEY=...`.
- **Free tier:** free developer tier with per-minute and daily request/token
  caps; the fastest tokens/sec you can get for free. No card.

### 3. Groq — `GROQ_API_KEY`
1. Go to <https://console.groq.com/keys>.
2. Sign in → **Create API Key** → copy (shown once).
3. Set `GROQ_API_KEY=...`.
- **Free tier:** ~30 requests/min and a daily token budget per model. No card.

### 4. SambaNova — `SAMBANOVA_API_KEY`
1. Go to <https://cloud.sambanova.ai> and sign up.
2. Open **APIs** / **API Keys** → generate a key → copy.
3. Set `SAMBANOVA_API_KEY=...`.
- **Free tier:** free developer access to DeepSeek R1 and Llama models with
  rate limits. No card.

### 5. NVIDIA NIM (build.nvidia.com) — `NVIDIA_API_KEY`
1. Go to <https://build.nvidia.com> and sign in (free NVIDIA developer account).
2. Pick any model → **Get API Key** / **Generate Key** → copy (starts `nvapi-`).
3. Set `NVIDIA_API_KEY=...`.
- **Free tier:** ~1,000 free credits on signup; OpenAI-compatible endpoint. No card.

### 6. Mistral (La Plateforme) — `MISTRAL_API_KEY`
1. Go to <https://console.mistral.ai/api-keys>.
2. Sign up and complete account setup.
3. **Create new key** → copy.
4. Set `MISTRAL_API_KEY=...`.
- **Free tier:** the "Experiment" free plan with rate limits. May ask for phone
  verification.

### 7. OpenRouter — `OPENROUTER_API_KEY`
1. Go to <https://openrouter.ai/keys>.
2. Sign in (Google/GitHub) → **Create Key** → copy (starts `sk-or-`).
3. Set `OPENROUTER_API_KEY=...`.
- **Free tier:** many models with a `:free` suffix are permanently free behind a
  single key (rate-limited per day). No card for the free models.

### 8. GitHub Models — `GITHUB_MODELS_TOKEN`
1. Go to <https://github.com/settings/tokens> → **Fine-grained tokens** →
   **Generate new token**.
2. Under **Permissions → Account permissions**, grant **Models: Read-only**.
3. Generate and copy the token (starts `github_pat_`).
4. Set `GITHUB_MODELS_TOKEN=...`.
- **Free tier:** free for any GitHub account, with per-minute/day request caps.
  Browse models at <https://github.com/marketplace/models>.

### 9. Cohere — `COHERE_API_KEY`
1. Go to <https://dashboard.cohere.com/api-keys>.
2. Sign up → copy the **Trial key** (already created for you).
3. Set `COHERE_API_KEY=...`.
- **Free tier:** trial keys are rate-limited (good for low-volume use). No card.

### 10. Cloudflare Workers AI — `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`
This is the one provider that needs **two** values.
1. Sign in at <https://dash.cloudflare.com>.
2. Your **Account ID** is in the URL and on the account/Workers&Pages overview —
   copy it into `CLOUDFLARE_ACCOUNT_ID`.
3. Go to **My Profile → API Tokens → Create Token**, use the **Workers AI**
   template (or a custom token with the *Workers AI: Read* permission) → copy.
4. Set `CLOUDFLARE_API_TOKEN=...` and `CLOUDFLARE_ACCOUNT_ID=...`.
- **Free tier:** ~10,000 "neurons"/day of inference. No card.

---

## After you have keys

```bash
cp .env.example .env      # then paste your keys in
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://localhost:8000> to chat, or check which providers came online:

```bash
curl http://localhost:8000/providers
```

Any provider whose key is missing simply shows `enabled: false` and is skipped —
no errors. Add keys over time; the gateway picks them up on restart.

---

## Tips for maximizing free usage

- **Add as many providers as you can.** The gateway always tries the best model
  first and only falls back when one is rate-limited, so extra keys = more
  headroom, not more cost.
- **Keys are secrets.** `.env` is gitignored — never commit it. For deployment,
  set the variables in your host's secret manager instead of a file.
- **Some "free trials" expire or need a card** (e.g. paid clouds). Everything in
  this list is a standing free tier, not a trial, unless noted.
- **Respect the terms.** Free tiers are for development and personal use; check
  each provider's usage policy before anything production-facing.

## Sources

- [OpenRouter — Free LLM APIs in 2026, ranked & compared](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)
- [Analytics Vidhya — 15 Free LLM APIs (2026)](https://www.analyticsvidhya.com/blog/2026/01/top-free-llm-apis/)
- [TokenMix — Free LLM API 2026: limits & no-card picks](https://tokenmix.ai/blog/free-llm-api)
- [We The Flywheel — Best Free LLM API Tiers in 2026](https://wetheflywheel.com/en/ai-model-access/free-llm-api-tiers-2026/)
- [NVIDIA NIM Free API — rate limits & keys](https://decodethefuture.org/en/nvidia-nim-api-explained/)
- [awesome-free-llm-apis (GitHub)](https://github.com/amardeeplakshkar/awesome-free-llm-apis)
