"""Dishari LLM module: Provider-agnostic wrapper for all LLM calls."""

from llm.cache import DiskCache
from llm.client import LLMClient, complete, get_default_client
from llm.job_queue import JobQueue
from llm.prompt_loader import load_prompt
from llm.providers.adapters import (
    FakeProvider,
    GeminiProvider,
    GroqProvider,
    OllamaProvider,
    OpenRouterProvider,
    create_provider,
)
from llm.providers.base import BaseProvider
from llm.rate_limiter import RateLimiter
from llm.types import (
    LLMError,
    LLMResponse,
    MaxRetriesExceededError,
    PromptNotFoundError,
    PromptTemplate,
    ProviderUnavailableError,
    RateLimitError,
    SchemaValidationError,
    UsageRecord,
)
from llm.usage_logger import UsageLogger

__all__ = [
    "complete",
    "LLMClient",
    "get_default_client",
    "DiskCache",
    "JobQueue",
    "RateLimiter",
    "UsageLogger",
    "load_prompt",
    "BaseProvider",
    "GeminiProvider",
    "GroqProvider",
    "OpenRouterProvider",
    "OllamaProvider",
    "FakeProvider",
    "create_provider",
    "LLMError",
    "RateLimitError",
    "ProviderUnavailableError",
    "SchemaValidationError",
    "MaxRetriesExceededError",
    "PromptNotFoundError",
    "PromptTemplate",
    "LLMResponse",
    "UsageRecord",
]
