"""
FastAPI app exposing the multi-provider chat gateway.

Endpoints
    GET  /healthz                  liveness
    GET  /providers                per-provider status (enabled / cooldown / stats)
    POST /chat                     friendly chat: {"message": "..."} -> {"content": ...}
    POST /chat/stream              same, streamed as Server-Sent Events
    POST /v1/chat/completions      OpenAI-compatible (works with the openai SDK)
    GET  /                         tiny browser chat UI
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from .config import settings
from .providers import PROVIDERS
from .router import AllProvidersExhausted, router
from .schemas import (
    ChatRequest,
    ChatResponse,
    OpenAIChatRequest,
    ProviderStatus,
)

app = FastAPI(
    title="Free LLM Chat Gateway",
    version="1.0.0",
    description="Chat over many free LLM providers with automatic failover.",
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# --- optional gateway auth -------------------------------------------------
def require_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    """If GATEWAY_API_KEY is set, require it on protected endpoints."""
    expected = settings.gateway_api_key
    if not expected:
        return
    presented = x_api_key or (
        authorization.removeprefix("Bearer ").strip()
        if authorization and authorization.lower().startswith("bearer ")
        else authorization
    )
    if presented != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# --- meta ------------------------------------------------------------------
@app.get("/healthz")
def healthz() -> dict:
    enabled = [p.name for p in PROVIDERS if p.enabled]
    return {"status": "ok", "enabled_providers": enabled}


@app.get("/providers", response_model=list[ProviderStatus])
def providers() -> list[ProviderStatus]:
    now = time.time()
    out: list[ProviderStatus] = []
    for p in PROVIDERS:
        state = router.state(p)
        out.append(
            ProviderStatus(
                name=p.name,
                enabled=p.enabled,
                models=[m.id for m in p.models],
                cooldown_seconds_left=state.cooldown_left(now),
                disabled_reason=state.disabled_reason
                or (None if p.enabled else f"no key ({p.api_key_env})"),
                successes=state.successes,
                failures=state.failures,
            )
        )
    return out


# --- chat ------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_key)])
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        messages = req.to_messages()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        result = await router.complete(
            messages,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except AllProvidersExhausted as e:
        raise HTTPException(
            status_code=503,
            detail={"error": str(e), "attempts": e.attempts},
        )
    return ChatResponse(
        content=result.content,
        provider=result.provider,
        model=result.model,
        latency_ms=result.latency_ms,
        attempts=result.attempts,
        usage=result.usage,
    )


@app.post("/chat/stream", dependencies=[Depends(require_key)])
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    try:
        messages = req.to_messages()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    async def gen():
        try:
            chosen = None
            async for route, delta in router.stream(
                messages,
                model=req.model,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            ):
                if chosen is None:
                    chosen = route
                    yield _sse({"event": "route", "provider": route.provider.name,
                                "model": route.model.id})
                yield _sse({"event": "delta", "content": delta})
            yield _sse({"event": "done"})
        except AllProvidersExhausted as e:
            yield _sse({"event": "error", "error": str(e), "attempts": e.attempts})

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- OpenAI-compatible -----------------------------------------------------
@app.post("/v1/chat/completions", dependencies=[Depends(require_key)])
async def openai_compatible(req: OpenAIChatRequest):
    messages = [m.model_dump() for m in req.messages]
    created = int(time.time())
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    if req.stream:
        async def gen():
            model_id = req.model
            try:
                async for route, delta in router.stream(
                    messages, model=req.model,
                    temperature=req.temperature, max_tokens=req.max_tokens,
                ):
                    model_id = f"{route.provider.name}/{route.model.id}"
                    yield _sse(_openai_chunk(cid, created, model_id, delta))
                yield _sse(_openai_chunk(cid, created, model_id, None, finish="stop"))
                yield "data: [DONE]\n\n"
            except AllProvidersExhausted as e:
                yield _sse({"error": {"message": str(e), "type": "all_providers_exhausted"}})

        return StreamingResponse(gen(), media_type="text/event-stream")

    try:
        result = await router.complete(
            messages, model=req.model,
            temperature=req.temperature, max_tokens=req.max_tokens,
        )
    except AllProvidersExhausted as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "id": cid,
        "object": "chat.completion",
        "created": created,
        "model": f"{result.provider}/{result.model}",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": "stop",
            }
        ],
        "usage": result.usage or {},
    }


# --- UI --------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# --- helpers ---------------------------------------------------------------
def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _openai_chunk(cid, created, model, content, finish=None) -> dict:
    delta = {} if content is None else {"content": content}
    return {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
