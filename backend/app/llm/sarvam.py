"""Thin client for Sarvam's OpenAI-compatible chat endpoint (model: sarvam-105b).

Why a hand-written client: it is ~60 lines, has no extra dependency, and lets us
handle three real-world quirks in one place:
  1. sarvam-105b is a reasoning model -> it may wrap output in <think> tags or
     return empty `content` if reasoning used up max_tokens.
  2. 429 / 5xx errors -> retried with exponential backoff.
  3. `response_format=json_object` -> used when accepted, dropped on a 400.
"""
import json
import re
import time

import httpx

from ..config import settings


class LLMError(Exception):
    pass


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (handles ``` fences)."""
    text = _strip_think(text)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError(f"No JSON object in model reply: {text[:200]!r}")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON from model: {e}") from e


class SarvamClient:
    def __init__(self):
        self._http = httpx.Client(
            base_url=settings.sarvam_base_url,
            timeout=settings.llm_timeout_seconds,
            headers={"api-subscription-key": settings.sarvam_api_key, "Content-Type": "application/json"},
        )

    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int | None = None,
             json_mode: bool = False) -> str:
        if not settings.sarvam_api_key:
            raise LLMError("SARVAM_API_KEY is not set in backend/.env")
        payload = {
            "model": settings.sarvam_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or settings.llm_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last = ""
        for attempt in range(4):
            try:
                r = self._http.post("/chat/completions", json=payload)
            except httpx.HTTPError as e:
                last = str(e)
                time.sleep(2**attempt)
                continue
            if r.status_code == 400 and "response_format" in payload:
                payload.pop("response_format")  # model/endpoint rejected JSON mode; prompt still asks for JSON
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"HTTP {r.status_code}"
                time.sleep(2**attempt)
                continue
            if r.status_code >= 400:
                raise LLMError(f"Sarvam API {r.status_code}: {r.text[:300]}")
            choice = r.json()["choices"][0]
            content = _strip_think(choice["message"].get("content") or "")
            if not content:
                hint = " (reasoning used all tokens - raise LLM_MAX_TOKENS)" if choice.get("finish_reason") == "length" else ""
                raise LLMError("Empty reply from model" + hint)
            return content
        raise LLMError(f"Sarvam API unavailable after retries: {last}")

    def chat_json(self, messages: list[dict], **kw) -> dict:
        return extract_json(self.chat(messages, json_mode=True, **kw))


llm = SarvamClient()
