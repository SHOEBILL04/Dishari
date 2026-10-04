"""Base interface for LLM provider adapters."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from llm.types import LLMResponse


class BaseProvider(ABC):
    """Abstract base class that all provider adapters must implement."""

    def __init__(
        self,
        name: str,
        model: str,
        cost_input_per_million: float = 0.0,
        cost_output_per_million: float = 0.0,
        max_retries_on_429: int = 3,
        backoff_initial_sec: float = 1.0,
    ):
        self.name = name
        self.model = model
        self.cost_input_per_million = cost_input_per_million
        self.cost_output_per_million = cost_output_per_million
        self.max_retries_on_429 = max_retries_on_429
        self.backoff_initial_sec = backoff_initial_sec

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD based on token counts."""
        input_cost = (input_tokens / 1_000_000.0) * self.cost_input_per_million
        output_cost = (output_tokens / 1_000_000.0) * self.cost_output_per_million
        return round(input_cost + output_cost, 6)

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        """Execute completion request and return standardized LLMResponse.
        
        Must raise RateLimitError on HTTP 429 status code.
        Must raise ProviderUnavailableError on network/5xx failures.
        """
        pass
