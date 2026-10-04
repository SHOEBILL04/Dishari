"""Type definitions and custom exceptions for the LLM wrapper."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


class LLMError(Exception):
    """Base exception for all LLM wrapper errors."""
    pass


class PromptNotFoundError(LLMError):
    """Raised when a requested prompt template cannot be found."""
    pass


class RateLimitError(LLMError):
    """Raised when request limits (per minute or per day) are exceeded."""
    def __init__(self, message: str, retry_after_sec: float = 0.0):
        super().__init__(message)
        self.retry_after_sec = retry_after_sec


class ProviderUnavailableError(LLMError):
    """Raised when an LLM provider is unreachable or returns a server error."""
    pass


class SchemaValidationError(LLMError):
    """Raised when LLM output fails schema validation."""
    pass


class MaxRetriesExceededError(LLMError):
    """Raised when all retries and fallback providers have failed."""
    pass


@dataclass
class PromptTemplate:
    """Represents a loaded prompt markdown template."""
    name: str
    version: str
    description: str
    system_prompt: Optional[str]
    template_text: str
    rendered_text: str


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider adapter."""
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    latency_ms: float
    raw_response: Optional[dict[str, Any]] = None


@dataclass
class UsageRecord:
    """Record of an individual LLM call for auditing and cost estimation."""
    call_id: str
    timestamp: datetime
    prompt_name: str
    prompt_version: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: float
    cache_hit: bool
    status: str  # 'success', 'retry', 'fallback', 'failed'
    error_message: Optional[str] = None
