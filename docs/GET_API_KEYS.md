# How to collect free LLM API keys

This gateway works with any number of providers — **even one key is enough to
start**. Add more to get more total free capacity and longer uptime before
everything is rate-limited at once.

> **Read this first — "free" has fine print (verified June 2026).**
> The market shifted in 2026. Some providers that used to be the obvious pick
> now want money up front. The biggest change: **Google Gemini** now requires
> **prepaid billing for new Google AI Studio accounts** (since ~March 2026) and
> moved its Pro models to paid in April — so for a fresh account it is *not*
> truly free anymore. The list below is split into what is **permanently free
> (no card, no expiry)** vs. **trial / prepaid / restricted**.

The gateway encodes this: permanent-free providers are tried first, and
`GET /providers` shows each provider's `permanent_free` flag and a `free_note`.

After you collect keys, put them in a `.env` file in the repo root (copy
`.env.example`).

---

## ✅ Truly free — no credit card, no expiry (use these)

Start here. Even one of these keeps the gateway running for free indefinitely.

| Provider | Env var | Free tier (approx, 2026) | Caveat |
|---|---|---|---|
| **Groq** | `GROQ_API_KEY` | ~14,400 req/day, 30k tok/min/model; very fast | — |
| **Cerebras** | `CEREBRAS_API_KEY` | ~1,000,000 tokens/day; fastest inference | 8k-token context cap on free tier |
| **OpenRouter** | `OPENROUTER_API_KEY` | many `:free` models; ~50 req/day | rises to 1,000/day only after a one-time $10 top-up |
| **GitHub Models** | `GITHUB_MODELS_TOKEN` | free for any GitHub account | per-minute/day caps |
| **Cloudflare Workers AI** | `CLOUDFLARE_API_TOKEN` (+ `CLOUDFLARE_ACCOUNT_ID`) | ~10,000 neurons/day | needs your account id too |
| **Mistral** | `MISTRAL_API_KEY` | ~1B tokens/month ("Experiment") | **must opt into data-training** to use the free tier |
| **SambaNova** | `SAMBANOVA_API_KEY` | permanent ~20 RPM / 200k tok/day | also grants $5 bonus credits that *do* expire |

### Recommended minimum: **Groq + Cerebras**
Both are no-card, permanent, and fast, and between them you get Llama 3.3 70B,
GPT-OSS 120B, and Qwen — enough to run the whole app for free with comfortable
daily limits. Add OpenRouter and GitHub Models next for breadth (DeepSeek R1,
GPT-4.1).

---

## ⚠️ Trial / prepaid / restricted — not "free forever"

Kept in the registry so you can use them *if* you have credits or an existing
account, but they're deprioritized and flagged. Don't rely on them as your base.

| Provider | Env var | Why it's flagged |
|---|---|---|
| **Google Gemini** | `GEMINI_API_KEY` | **New AI Studio accounts now require prepaid billing**; Pro is paid. Only *existing* accounts still get Gemini Flash on the free tier. |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Trial credits that **expire** (~5,000 credits / ~30 days), not a standing free tier. |
| **Cohere** | `COHERE_API_KEY` | Trial key (1,000 calls/mo, resets) but **not permitted for production/commercial use**. |

If you already have a Gemini key on an older free account, set `GEMINI_API_KEY`
and it'll be used — just not preferred over the permanent-free providers.

---

## Step-by-step: getting each key

### Groq — `GROQ_API_KEY`  *(✅ truly free)*
1. Go to <https://console.groq.com/keys> and sign in.
2. **Create API Key** → copy (shown once).
3. Set `GROQ_API_KEY=...`.

### Cerebras — `CEREBRAS_API_KEY`  *(✅ truly free)*
1. Sign up at <https://cloud.cerebras.ai> (Google/GitHub/email).
2. **API Keys → Create API Key** → copy.
3. Set `CEREBRAS_API_KEY=...`.

### OpenRouter — `OPENROUTER_API_KEY`  *(✅ truly free)*
1. Go to <https://openrouter.ai/keys>, sign in (Google/GitHub).
2. **Create Key** → copy (starts `sk-or-`).
3. Set `OPENROUTER_API_KEY=...`. Use the `:free` models (already configured).

### GitHub Models — `GITHUB_MODELS_TOKEN`  *(✅ truly free)*
1. <https://github.com/settings/tokens> → **Fine-grained tokens** →
   **Generate new token**.
2. Under **Account permissions**, grant **Models: Read-only**.
3. Generate → copy (starts `github_pat_`).
4. Set `GITHUB_MODELS_TOKEN=...`.

### Cloudflare Workers AI — `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`  *(✅ truly free)*
1. Sign in at <https://dash.cloudflare.com>.
2. Copy your **Account ID** (in the URL / Workers & Pages overview) →
   `CLOUDFLARE_ACCOUNT_ID`.
3. **My Profile → API Tokens → Create Token** → use the **Workers AI** template
   (or a custom token with *Workers AI: Read*) → copy.
4. Set `CLOUDFLARE_API_TOKEN=...` and `CLOUDFLARE_ACCOUNT_ID=...`.

### Mistral — `MISTRAL_API_KEY`  *(✅ truly free, with a condition)*
1. Go to <https://console.mistral.ai/api-keys> and sign up.
2. Opt into the free **Experiment** plan (this **allows Mistral to train on your
   data** — required for the free tier).
3. **Create new key** → copy. Set `MISTRAL_API_KEY=...`.

### SambaNova — `SAMBANOVA_API_KEY`  *(✅ truly free base tier)*
1. Sign up at <https://cloud.sambanova.ai>.
2. **APIs / API Keys** → generate → copy.
3. Set `SAMBANOVA_API_KEY=...`.

### Google Gemini — `GEMINI_API_KEY`  *(⚠️ prepaid for new accounts)*
1. <https://aistudio.google.com/apikey> → **Create API key**.
2. New accounts are now prompted to set up **prepaid billing** (buy credits
   first). If you're fine with that, or you have an older free account, copy the
   key and set `GEMINI_API_KEY=...`. Otherwise skip it — the truly-free
   providers above cover you.

### NVIDIA NIM — `NVIDIA_API_KEY`  *(⚠️ expiring trial credits)*
1. <https://build.nvidia.com> → sign in → pick a model → **Get API Key**
   (starts `nvapi-`). 2. Set `NVIDIA_API_KEY=...`. Note the credits expire.

### Cohere — `COHERE_API_KEY`  *(⚠️ non-commercial trial)*
1. <https://dashboard.cohere.com/api-keys> → copy the **Trial key**.
2. Set `COHERE_API_KEY=...`. Personal/eval use only.

---

## After you have keys

```bash
cp .env.example .env      # paste your keys in
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://localhost:8000> to chat, or check what came online and whether each
is permanent-free:

```bash
curl -s http://localhost:8000/providers | python3 -m json.tool
```

Any provider whose key is missing simply shows `enabled: false` and is skipped.

## Tips

- **Add several permanent-free keys.** The gateway tries the best model first
  and falls back only when one is rate-limited, so more keys = more headroom.
- **Keys are secrets.** `.env` is gitignored — never commit it. In production,
  use your host's secret manager.
- **Respect each provider's terms** (e.g. Cohere trial = non-commercial,
  Mistral free = data-training opt-in).

## Sources

- [Gemini free tier tightened — Pro paid from April 2026](https://help.apiyi.com/en/google-gemini-api-free-tier-changes-april-2026-guide-en.html)
- [Gemini free tier: new accounts may require prepaid billing](https://www.aifreeapi.com/en/posts/google-gemini-api-free-tier)
- [Ian Paterson — What Groq, Cerebras, Mistral, Gemini, Cohere actually give you (2026)](https://ianlpaterson.com/blog/free-llm-api-2026/)
- [Cerebras now has a real free tier (1M tokens/day)](https://tokenmix.ai/blog/cerebras-api-key-rate-limits-free-tier-2026)
- [Groq free tier — no credit card](https://www.getaiperks.com/en/ai/groq-free-tier-2026)
- [OpenRouter free models & limits](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)
- [awesome-free-llm-apis — permanent free list](https://github.com/mnfst/awesome-free-llm-apis)
- [NVIDIA NIM credits expire (developer forum)](https://forums.developer.nvidia.com/t/your-free-nvidia-api-credits-expire-in-2-days/318141)
- [Cohere trial key limits (non-commercial)](https://codenote.net/en/posts/cohere-trial-api-key-pricing-and-limits/)
