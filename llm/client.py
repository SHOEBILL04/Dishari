"""Unified provider-agnostic LLM client for Dishari.

Orchestrates prompt loading, version logging, caching, rate limiting,
exponential backoff, provider fallback, and strict Pydantic JSON schema validation.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import random
import re
import time
from typing import Any, Optional, Type, Union
import uuid
import yaml
from pydantic import BaseModel, ValidationError

from llm.cache import DiskCache
from llm.prompt_loader import load_prompt
from llm.providers.adapters import BaseProvider, create_provider
from llm.rate_limiter import RateLimiter
from llm.types import (
    LLMError,
    MaxRetriesExceededError,
    ProviderUnavailableError,
    RateLimitError,
    SchemaValidationError,
    UsageRecord,
)
from llm.usage_logger import UsageLogger

logger = logging.getLogger("dishari.llm")
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "llm.yaml"


def _clean_json_markdown(content: str) -> str:
    """Strip markdown code fence backticks from LLM output if present."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


class LLMClient:
    """Provider-agnostic LLM interface with caching, rate limiting, and fallbacks."""

    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        config_path: Optional[Union[str, Path]] = None,
        cache: Optional[DiskCache] = None,
        rate_limiter: Optional[RateLimiter] = None,
        usage_logger: Optional[UsageLogger] = None,
        providers: Optional[dict[str, BaseProvider]] = None,
        active_chain: Optional[list[str]] = None,
        prompts_dir: Optional[Path] = None,
    ):
        if config is not None:
            self.config = config
        else:
            cfg_file = Path(config_path or DEFAULT_CONFIG_PATH)
            if cfg_file.is_file():
                self.config = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
            else:
                self.config = {}

        # Set up components
        cache_cfg = self.config.get("cache", {})
        self.cache_enabled = cache_cfg.get("enabled", True)
        cache_path = cache_cfg.get("db_path", "data/llm_cache.sqlite")
        self.cache = cache or DiskCache(cache_path)

        usage_cfg = self.config.get("usage_log", {})
        usage_path = usage_cfg.get("db_path", "data/llm_usage.sqlite")
        self.usage_logger = usage_logger or UsageLogger(usage_path)

        self.rate_limiter = rate_limiter or RateLimiter(usage_path)
        self.prompts_dir = prompts_dir or (Path(__file__).resolve().parent.parent / "prompts")

        # Set up providers and fallback chain
        self.active_chain = active_chain or self.config.get("active_chain", ["gemini", "groq"])
        self.providers: dict[str, BaseProvider] = providers or {}

        if not self.providers and "providers" in self.config:
            for p_name, p_cfg in self.config["providers"].items():
                try:
                    self.providers[p_name] = create_provider(
                        p_cfg.get("adapter", p_name),
                        p_cfg
                    )
                except Exception as exc:
                    logger.warning("Failed to initialize provider '%s': %s", p_name, exc)

    def register_provider(self, name: str, provider: BaseProvider) -> None:
        """Register or override a provider adapter."""
        self.providers[name] = provider
        if name not in self.active_chain:
            self.active_chain.append(name)

    def _validate_output(
        self,
        raw_text: str,
        schema: Union[Type[BaseModel], dict[str, Any]],
    ) -> tuple[Optional[Any], Optional[str]]:
        """Parse raw LLM output into JSON and validate against schema.
        
        Returns:
            Tuple of (validated_result, error_message).
        """
        cleaned = _clean_json_markdown(raw_text)
        try:
            parsed_json = json.loads(cleaned)
        except Exception as exc:
            return None, f"JSON syntax error: {exc}. Ensure your entire response is strictly valid JSON."

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                validated = schema.model_validate(parsed_json)
                return validated, None
            except ValidationError as exc:
                return None, f"Schema validation error:\n{exc}"
        elif isinstance(schema, dict):
            # Dict schema validation (basic keys check if required specified)
            return parsed_json, None
        else:
            return parsed_json, None

    def complete(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        schema: Union[Type[BaseModel], dict[str, Any]],
        temperature: float = 0.0,
    ) -> Any:
        """Execute a prompt completion with caching, rate limits, and provider fallbacks.
        
        Args:
            prompt_name: Name of prompt file in /prompts (e.g. 'tag_question').
            variables: Dict of variables to interpolate into prompt template.
            schema: Pydantic model class or JSON schema dict for output validation.
            temperature: Sampling temperature (default 0.0 for deterministic output).
            
        Returns:
            Validated Pydantic model instance or dict.
            
        Raises:
            MaxRetriesExceededError: If all retries and fallback providers fail.
            SchemaValidationError: If output cannot be coerced to schema after retry.
        """
        prompt_tpl = load_prompt(prompt_name, variables, self.prompts_dir)
        prompt_ver = prompt_tpl.version
        call_id = str(uuid.uuid4())

        # Extract schema dict for providers that accept structured schemas
        schema_dict = (
            schema.model_json_schema() 
            if (isinstance(schema, type) and issubclass(schema, BaseModel)) 
            else (schema if isinstance(schema, dict) else None)
        )

        # 1. Check Disk Cache
        # Determine primary model name for caching key
        primary_provider_name = self.active_chain[0] if self.active_chain else "default"
        primary_model = (
            self.providers[primary_provider_name].model 
            if primary_provider_name in self.providers 
            else "default"
        )
        cache_key = self.cache.compute_key(
            prompt_name=prompt_tpl.name,
            prompt_version=prompt_ver,
            variables=variables,
            model=primary_model,
            temperature=temperature,
        )

        if self.cache_enabled:
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                # Re-validate cached data against target schema
                if isinstance(schema, type) and issubclass(schema, BaseModel):
                    val_res = schema.model_validate(cached_data)
                else:
                    val_res = cached_data

                # Log cache hit
                self.usage_logger.log(
                    UsageRecord(
                        call_id=call_id,
                        timestamp=datetime.now(timezone.utc),
                        prompt_name=prompt_tpl.name,
                        prompt_version=prompt_ver,
                        provider=primary_provider_name,
                        model=primary_model,
                        input_tokens=0,
                        output_tokens=0,
                        estimated_cost=0.0,
                        latency_ms=0.0,
                        cache_hit=True,
                        status="success",
                    )
                )
                return val_res

        # 2. Iterate through provider fallback chain
        last_error: Optional[Exception] = None
        executed_prompt = prompt_tpl.rendered_text

        for provider_name in self.active_chain:
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            # Read rate limit configuration for provider
            p_cfg = self.config.get("providers", {}).get(provider_name, {})
            rl_cfg = p_cfg.get("rate_limit", {})
            rpm = rl_cfg.get("requests_per_minute", 60)
            rpd = rl_cfg.get("requests_per_day", 100000)

            # Check rate limit
            acquired = self.rate_limiter.acquire_or_wait(provider_name, rpm, rpd, max_wait_sec=2.0)
            if not acquired:
                logger.warning("Provider '%s' rate limit reached. Falling back.", provider_name)
                self.usage_logger.log(
                    UsageRecord(
                        call_id=call_id,
                        timestamp=datetime.now(timezone.utc),
                        prompt_name=prompt_tpl.name,
                        prompt_version=prompt_ver,
                        provider=provider_name,
                        model=provider.model,
                        input_tokens=0,
                        output_tokens=0,
                        estimated_cost=0.0,
                        latency_ms=0.0,
                        cache_hit=False,
                        status="fallback",
                        error_message="Rate limit window saturated",
                    )
                )
                continue

            # Execute provider call with retry & exponential backoff on 429
            response = None
            for attempt in range(provider.max_retries_on_429):
                try:
                    response = provider.generate(
                        prompt=executed_prompt,
                        system_prompt=prompt_tpl.system_prompt,
                        temperature=temperature,
                        schema=schema_dict,
                    )
                    break
                except RateLimitError as rl_err:
                    last_error = rl_err
                    if attempt < provider.max_retries_on_429 - 1:
                        backoff = min(
                            30.0,
                            (provider.backoff_initial_sec * (2 ** attempt)) + random.uniform(0.1, 0.5)
                        )
                        logger.warning(
                            "Provider '%s' 429 encountered. Backing off for %.2fs (attempt %d).",
                            provider_name, backoff, attempt + 1
                        )
                        time.sleep(backoff)
                    else:
                        logger.warning(
                            "Provider '%s' max 429 retries exceeded. Falling back to next provider.",
                            provider_name
                        )
                except ProviderUnavailableError as pu_err:
                    last_error = pu_err
                    logger.warning("Provider '%s' unavailable: %s. Falling back.", provider_name, pu_err)
                    break

            if response is None:
                continue

            # 3. Schema validation with single retry on failure
            validated_obj, validation_err = self._validate_output(response.content, schema)
            cost = provider.calculate_cost(response.input_tokens, response.output_tokens)

            if validation_err is not None:
                logger.warning(
                    "Invalid JSON from provider '%s'. Retrying once with error feedback.",
                    provider_name
                )
                # Log initial failed attempt
                self.usage_logger.log(
                    UsageRecord(
                        call_id=call_id,
                        timestamp=datetime.now(timezone.utc),
                        prompt_name=prompt_tpl.name,
                        prompt_version=prompt_ver,
                        provider=provider_name,
                        model=provider.model,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        estimated_cost=cost,
                        latency_ms=response.latency_ms,
                        cache_hit=False,
                        status="retry",
                        error_message=validation_err,
                    )
                )

                # Append error message to prompt and retry ONCE
                retry_prompt = (
                    f"{executed_prompt}\n\n"
                    f"[CORRECTION REQUIRED]\n"
                    f"Your previous output failed validation:\n{validation_err}\n"
                    f"Please correct the errors and output ONLY valid JSON matching the schema."
                )

                try:
                    retry_resp = provider.generate(
                        prompt=retry_prompt,
                        system_prompt=prompt_tpl.system_prompt,
                        temperature=temperature,
                        schema=schema_dict,
                    )
                    retry_cost = provider.calculate_cost(retry_resp.input_tokens, retry_resp.output_tokens)
                    validated_obj, validation_err = self._validate_output(retry_resp.content, schema)

                    if validation_err is None:
                        # Retry succeeded!
                        cost += retry_cost
                        response = retry_resp
                    else:
                        # Retry failed as well
                        self.usage_logger.log(
                            UsageRecord(
                                call_id=call_id,
                                timestamp=datetime.now(timezone.utc),
                                prompt_name=prompt_tpl.name,
                                prompt_version=prompt_ver,
                                provider=provider_name,
                                model=provider.model,
                                input_tokens=retry_resp.input_tokens,
                                output_tokens=retry_resp.output_tokens,
                                estimated_cost=retry_cost,
                                latency_ms=retry_resp.latency_ms,
                                cache_hit=False,
                                status="failed",
                                error_message=validation_err,
                            )
                        )
                        last_error = SchemaValidationError(validation_err)
                        continue
                except Exception as retry_exc:
                    last_error = retry_exc
                    continue

            # Output is valid! Save to cache and log successful usage
            if self.cache_enabled:
                to_cache = (
                    validated_obj.model_dump() 
                    if hasattr(validated_obj, "model_dump") 
                    else validated_obj
                )
                self.cache.set(
                    cache_key=cache_key,
                    prompt_name=prompt_tpl.name,
                    prompt_version=prompt_ver,
                    model=provider.model,
                    response_data=to_cache,
                )

            self.usage_logger.log(
                UsageRecord(
                    call_id=call_id,
                    timestamp=datetime.now(timezone.utc),
                    prompt_name=prompt_tpl.name,
                    prompt_version=prompt_ver,
                    provider=provider_name,
                    model=provider.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    estimated_cost=cost,
                    latency_ms=response.latency_ms,
                    cache_hit=False,
                    status="success",
                )
            )

            return validated_obj

        # If we exited loop without returning, all providers in the fallback chain failed
        self.usage_logger.log(
            UsageRecord(
                call_id=call_id,
                timestamp=datetime.now(timezone.utc),
                prompt_name=prompt_tpl.name,
                prompt_version=prompt_ver,
                provider="all",
                model="all",
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0.0,
                latency_ms=0.0,
                cache_hit=False,
                status="failed",
                error_message=str(last_error),
            )
        )
        raise MaxRetriesExceededError(
            f"All providers in the fallback chain failed for prompt '{prompt_name}'. Last error: {last_error}"
        )


# Global default client instance
_default_client: Optional[LLMClient] = None


def get_default_client() -> LLMClient:
    """Return or initialize singleton default LLMClient."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def complete(
    prompt_name: str,
    variables: dict[str, Any],
    schema: Union[Type[BaseModel], dict[str, Any]],
    temperature: float = 0.0,
    client: Optional[LLMClient] = None,
) -> Any:
    """Convenience functional interface matching the user specification:
    complete(prompt_name, variables, schema, temperature) -> validated JSON.
    """
    active_client = client or get_default_client()
    return active_client.complete(
        prompt_name=prompt_name,
        variables=variables,
        schema=schema,
        temperature=temperature,
    )
