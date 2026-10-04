"""Provider adapters for Gemini, Groq, OpenRouter, Ollama, and Fake (testing)."""

import json
import os
import time
from typing import Any, Callable, Optional
import requests

from llm.providers.base import BaseProvider
from llm.types import LLMResponse, ProviderUnavailableError, RateLimitError


class GeminiProvider(BaseProvider):
    """Adapter for Google Gemini API."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key_env: str = "GEMINI_API_KEY",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        **kwargs: Any,
    ):
        super().__init__(name="gemini", model=model, **kwargs)
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderUnavailableError(
                f"Missing API key for Gemini in environment variable {self.api_key_env}"
            )

        url = f"{self.base_url}/models/{self.model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instruction:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow your instructions and reply in JSON."}]})

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            }
        }

        if schema:
            payload["generationConfig"]["responseSchema"] = schema

        start_time = time.perf_counter()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30.0)
        except requests.RequestException as exc:
            raise ProviderUnavailableError(f"Gemini connection failed: {exc}")

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 2.0))
            raise RateLimitError("Gemini rate limit exceeded (HTTP 429)", retry_after_sec=retry_after)

        if resp.status_code >= 500:
            raise ProviderUnavailableError(f"Gemini server error (HTTP {resp.status_code}): {resp.text}")

        if not resp.ok:
            raise ProviderUnavailableError(f"Gemini request failed (HTTP {resp.status_code}): {resp.text}")

        data = resp.json()
        try:
            candidates = data.get("candidates", [])
            content_text = candidates[0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount", 0)
            output_tokens = usage.get("candidatesTokenCount", 0)
        except (IndexError, KeyError) as exc:
            raise ProviderUnavailableError(f"Failed to extract candidate content from Gemini response: {exc}")

        return LLMResponse(
            content=content_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider=self.name,
            latency_ms=latency_ms,
            raw_response=data,
        )


class OpenAICompatibleProvider(BaseProvider):
    """Reusable adapter for OpenAI-compatible REST APIs (Groq, OpenRouter)."""

    def __init__(
        self,
        name: str,
        model: str,
        api_key_env: str,
        base_url: str,
        **kwargs: Any,
    ):
        super().__init__(name=name, model=model, **kwargs)
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderUnavailableError(
                f"Missing API key for {self.name} in environment variable {self.api_key_env}"
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        start_time = time.perf_counter()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30.0)
        except requests.RequestException as exc:
            raise ProviderUnavailableError(f"{self.name} connection failed: {exc}")

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 2.0))
            raise RateLimitError(f"{self.name} rate limit exceeded (HTTP 429)", retry_after_sec=retry_after)

        if resp.status_code >= 500:
            raise ProviderUnavailableError(f"{self.name} server error (HTTP {resp.status_code}): {resp.text}")

        if not resp.ok:
            raise ProviderUnavailableError(f"{self.name} request failed (HTTP {resp.status_code}): {resp.text}")

        data = resp.json()
        try:
            content_text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        except (IndexError, KeyError) as exc:
            raise ProviderUnavailableError(f"Failed to parse choices from {self.name}: {exc}")

        return LLMResponse(
            content=content_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider=self.name,
            latency_ms=latency_ms,
            raw_response=data,
        )


class GroqProvider(OpenAICompatibleProvider):
    """Adapter for Groq."""
    def __init__(self, model: str = "llama-3.3-70b-versatile", **kwargs: Any):
        super().__init__(
            name="groq",
            model=model,
            api_key_env=kwargs.pop("api_key_env", "GROQ_API_KEY"),
            base_url=kwargs.pop("base_url", "https://api.groq.com/openai/v1"),
            **kwargs,
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    """Adapter for OpenRouter."""
    def __init__(self, model: str = "google/gemini-2.5-flash", **kwargs: Any):
        super().__init__(
            name="openrouter",
            model=model,
            api_key_env=kwargs.pop("api_key_env", "OPENROUTER_API_KEY"),
            base_url=kwargs.pop("base_url", "https://openrouter.ai/api/v1"),
            **kwargs,
        )


class OllamaProvider(BaseProvider):
    """Adapter for local Ollama instances."""

    def __init__(
        self,
        model: str = "mistral:latest",
        base_url: str = "http://localhost:11434",
        **kwargs: Any,
    ):
        super().__init__(name="ollama", model=model, **kwargs)
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        url = f"{self.base_url}/api/chat"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }

        start_time = time.perf_counter()
        try:
            resp = requests.post(url, json=payload, timeout=60.0)
        except requests.RequestException as exc:
            raise ProviderUnavailableError(f"Ollama connection failed: {exc}")

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if not resp.ok:
            raise ProviderUnavailableError(f"Ollama request failed (HTTP {resp.status_code}): {resp.text}")

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider=self.name,
            latency_ms=latency_ms,
            raw_response=data,
        )


class FakeProvider(BaseProvider):
    """Programmable fake provider for unit tests without external API keys."""

    def __init__(
        self,
        name: str = "fake",
        model: str = "fake-model",
        responses: Optional[list[Any]] = None,
        raise_error: Optional[Exception] = None,
        **kwargs: Any,
    ):
        super().__init__(name=name, model=model, **kwargs)
        self.responses = responses or []
        self.raise_error = raise_error
        self.call_history: list[dict[str, Any]] = []

    def set_responses(self, responses: list[Any]) -> None:
        self.responses = list(responses)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        self.call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "schema": schema,
        })

        if self.raise_error:
            err = self.raise_error
            # If it's a list or callable, handle dynamic error
            if isinstance(err, list) and err:
                to_raise = err.pop(0)
                if to_raise:
                    raise to_raise
            elif isinstance(err, Exception):
                raise err

        if not self.responses:
            # Default fallback mock response
            content = "{}"
        else:
            item = self.responses.pop(0)
            if isinstance(item, Exception):
                raise item
            if isinstance(item, dict):
                content = json.dumps(item, ensure_ascii=False)
            else:
                content = str(item)

        return LLMResponse(
            content=content,
            input_tokens=50,
            output_tokens=25,
            model=self.model,
            provider=self.name,
            latency_ms=12.5,
        )


def create_provider(provider_type: str, config: dict[str, Any]) -> BaseProvider:
    """Factory creating an adapter from configuration."""
    ptype = provider_type.lower()
    cost_cfg = config.get("cost", {})
    common_args = {
        "model": config.get("model", "default-model"),
        "cost_input_per_million": cost_cfg.get("input_cost_per_million", 0.0),
        "cost_output_per_million": cost_cfg.get("output_cost_per_million", 0.0),
        "max_retries_on_429": config.get("max_retries_on_429", 3),
        "backoff_initial_sec": config.get("backoff_initial_sec", 1.0),
    }

    if ptype == "gemini":
        return GeminiProvider(
            api_key_env=config.get("api_key_env", "GEMINI_API_KEY"),
            base_url=config.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
            **common_args,
        )
    elif ptype == "groq":
        return GroqProvider(
            api_key_env=config.get("api_key_env", "GROQ_API_KEY"),
            base_url=config.get("base_url", "https://api.groq.com/openai/v1"),
            **common_args,
        )
    elif ptype == "openrouter":
        return OpenRouterProvider(
            api_key_env=config.get("api_key_env", "OPENROUTER_API_KEY"),
            base_url=config.get("base_url", "https://openrouter.ai/api/v1"),
            **common_args,
        )
    elif ptype == "ollama":
        return OllamaProvider(
            base_url=config.get("base_url", "http://localhost:11434"),
            **common_args,
        )
    elif ptype == "fake":
        return FakeProvider(**common_args)
    else:
        raise ValueError(f"Unknown provider adapter type: {provider_type}")
