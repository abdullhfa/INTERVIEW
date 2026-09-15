"""
AI Interview Coach - LLM Gateway (DeepSeek OpenAI-compatible API)

Provides the same interface previously used for Gemini text tasks.
Live STT remains in stt_engine (Google Web Speech; optional Gemini audio).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMGateway:
    """Unified interface for DeepSeek chat/completions."""

    def __init__(self) -> None:
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url.rstrip("/")
        self._default_model = settings.deepseek_model
        self._reasoning_model = settings.deepseek_model
        self._fast_model = settings.deepseek_model
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(120.0, connect=10.0),
                    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                )
            return self._client

    async def warm_connection(self) -> None:
        """Open the HTTP pool before the first live question to cut cold-start latency."""
        try:
            await self.generate_text(
                "ok",
                max_output_tokens=1,
                temperature=0.0,
                timeout_seconds=8.0,
            )
            logger.info("DeepSeek connection pre-warmed")
        except Exception as exc:
            logger.debug("DeepSeek warm-up skipped: %s", exc)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        timeout_seconds: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> T:
        schema_json = json.dumps(
            response_schema.model_json_schema(),
            ensure_ascii=False,
            indent=2,
        )
        system = (
            "You must respond with valid JSON only. "
            "No markdown fences, no commentary.\n"
            f"JSON schema:\n{schema_json}"
        )
        if system_instruction:
            system = f"{system_instruction.strip()}\n\n{system}"

        raw = await self.generate_text(
            prompt,
            system_instruction=system,
            model=model or self._fast_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens or 4096,
            timeout_seconds=timeout_seconds,
            json_mode=True,
        )
        return response_schema.model_validate_json(self._extract_json(raw))

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
        timeout_seconds: Optional[float] = None,
        thinking_budget: Optional[int] = None,
        json_mode: bool = False,
        disable_thinking: bool = True,
        skip_length_retry: bool = False,
    ) -> str:
        # DeepSeek v4 enables thinking by default. Reasoning tokens share
        # max_tokens with the visible answer, which truncates bilingual replies
        # and forces a slow second translation round-trip.
        del thinking_budget

        payload = self._completion_payload(
            prompt,
            system_instruction=system_instruction,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            stream=False,
            disable_thinking=disable_thinking,
            json_mode=json_mode,
        )

        text, finish_reason = await self._chat_completion(
            payload,
            timeout_seconds=timeout_seconds,
        )

        # A second full request roughly doubles live latency. Retry only when
        # the first reply is clearly truncated and not yet usable.
        if (
            not skip_length_retry
            and finish_reason == "length"
            and max_output_tokens < 8192
            and len((text or "").strip()) < 48
        ):
            payload["max_tokens"] = min(max_output_tokens * 2, 8192)
            text, _ = await self._chat_completion(payload, timeout_seconds=timeout_seconds)

        return text

    async def generate_text_stream(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
        timeout_seconds: Optional[float] = None,
        thinking_budget: Optional[int] = None,
        json_mode: bool = False,
        disable_thinking: bool = True,
        skip_length_retry: bool = False,
    ) -> AsyncIterator[str]:
        """Yield accumulated visible text as tokens arrive."""
        del thinking_budget, skip_length_retry

        payload = self._completion_payload(
            prompt,
            system_instruction=system_instruction,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            stream=True,
            disable_thinking=disable_thinking,
            json_mode=json_mode,
        )
        request_timeout = timeout_seconds or settings.llm_request_timeout_seconds
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        client = await self._get_client()
        accumulated = ""
        try:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=request_timeout,
            ) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", errors="replace")[:500]
                    logger.error("DeepSeek stream error %s: %s", response.status_code, detail)
                    response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            break
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choice = (event.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        accumulated += piece
                        yield accumulated
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"DeepSeek stream timed out after {request_timeout:g} seconds"
            ) from exc

    def _completion_payload(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str],
        model: Optional[str],
        temperature: float,
        max_output_tokens: int,
        stream: bool,
        disable_thinking: bool,
        json_mode: bool,
    ) -> dict[str, Any]:
        target_model = model or self._reasoning_model
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": stream,
        }
        if disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def reason(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        full_prompt = prompt
        if context:
            full_prompt = f"## Context\n{context}\n\n## Task\n{prompt}"

        return await self.generate_text(
            full_prompt,
            system_instruction=system_instruction,
            model=self._reasoning_model,
            temperature=0.4,
        )

    async def classify(
        self,
        text: str,
        response_schema: Type[T],
        *,
        system_instruction: Optional[str] = None,
    ) -> T:
        return await self.generate_structured(
            text,
            response_schema,
            system_instruction=system_instruction,
            model=self._fast_model,
            temperature=0.1,
        )

    async def _chat_completion(
        self,
        payload: dict[str, Any],
        *,
        timeout_seconds: Optional[float] = None,
    ) -> tuple[str, str]:
        request_timeout = timeout_seconds or settings.llm_request_timeout_seconds
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        client = await self._get_client()
        try:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=request_timeout,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"DeepSeek request timed out after {request_timeout:g} seconds"
            ) from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            logger.error("DeepSeek API error %s: %s", response.status_code, detail)
            response.raise_for_status()

        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = (message.get("content") or "").strip()
        finish_reason = str(choice.get("finish_reason") or "")
        return content, finish_reason

    @staticmethod
    def _extract_json(raw: str) -> str:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text


gemini = LLMGateway()
llm = gemini
