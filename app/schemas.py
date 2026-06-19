"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


# --- Simple /chat endpoint -------------------------------------------------
class ChatRequest(BaseModel):
    """The friendly endpoint: send a message (and optional prior history)."""

    message: Optional[str] = Field(
        default=None, description="A single user message. Use this OR `messages`."
    )
    messages: Optional[list[Message]] = Field(
        default=None, description="Full chat history. Use this OR `message`."
    )
    model: str = Field(
        default="auto",
        description="`auto` picks the best available model; or pin a model id "
        "(e.g. `llama-3.3-70b-versatile`) to force a specific one.",
    )
    system: Optional[str] = Field(
        default=None, description="Optional system prompt prepended to the chat."
    )
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    def to_messages(self) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if self.system:
            msgs.append({"role": "system", "content": self.system})
        if self.messages:
            msgs.extend(m.model_dump() for m in self.messages)
        if self.message:
            msgs.append({"role": "user", "content": self.message})
        if not msgs or all(m["role"] == "system" for m in msgs):
            raise ValueError("Provide `message` or a non-empty `messages` list.")
        return msgs


class ChatResponse(BaseModel):
    content: str
    provider: str
    model: str
    latency_ms: int
    attempts: list[str] = Field(
        default_factory=list,
        description="Routes tried before success, in order (for transparency).",
    )
    usage: Optional[dict[str, Any]] = None


# --- OpenAI-compatible passthrough ----------------------------------------
class OpenAIChatRequest(BaseModel):
    """A subset of OpenAI's /v1/chat/completions request. `model` may be
    `auto` (default routing) or a specific model id to pin."""

    model: str = "auto"
    messages: list[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False


class ProviderStatus(BaseModel):
    name: str
    enabled: bool
    models: list[str]
    cooldown_seconds_left: int
    disabled_reason: Optional[str] = None
    successes: int
    failures: int
