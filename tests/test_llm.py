"""Unit tests for Dishari LLM wrapper using FakeProvider (no real API keys)."""

import json
from pathlib import Path
import tempfile
import pytest
from pydantic import BaseModel, Field

from llm.cache import DiskCache
from llm.client import LLMClient
from llm.job_queue import JobQueue
from llm.prompt_loader import load_prompt
from llm.providers.adapters import FakeProvider
from llm.rate_limiter import RateLimiter
from llm.types import (
    MaxRetriesExceededError,
    PromptNotFoundError,
    RateLimitError,
    ProviderUnavailableError,
)
from llm.usage_logger import UsageLogger


# Sample Pydantic Schemas for testing
class QuestionTag(BaseModel):
    subject_code: str = Field(..., description="Subject identifier")
    topic_name: str = Field(..., description="Topic title")
    confidence: float = Field(..., ge=0.0, le=1.0)


class SolverOutput(BaseModel):
    chosen_index: int = Field(..., ge=0, le=3)
    reasoning: str


@pytest.fixture
def temp_dir():
    """Create a temporary directory for isolated sqlite databases and test prompts."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_prompts_dir(temp_dir):
    """Set up sample prompt markdown files with version headers."""
    prompts_path = temp_dir / "prompts"
    prompts_path.mkdir(parents=True, exist_ok=True)

    tag_prompt = prompts_path / "tag_question.md"
    tag_prompt.write_text(
        """---
version: 1.2.0
description: Tag BCS question
system: You are a classifier. Output JSON only.
---
Stem: {stem}
Options: {options}
Taxonomy: {taxonomy}
Output JSON:
""",
        encoding="utf-8"
    )

    return prompts_path


@pytest.fixture
def llm_env(temp_dir, sample_prompts_dir):
    """Set up an isolated LLM environment with fake providers."""
    cache = DiskCache(temp_dir / "cache.sqlite")
    usage_logger = UsageLogger(temp_dir / "usage.sqlite")
    rate_limiter = RateLimiter(temp_dir / "rate.sqlite")
    job_queue = JobQueue(temp_dir / "jobs.sqlite")

    primary_provider = FakeProvider(
        name="primary_fake",
        model="primary-model-v1",
        cost_input_per_million=1.0,
        cost_output_per_million=2.0,
        max_retries_on_429=2,
        backoff_initial_sec=0.01,
    )

    fallback_provider = FakeProvider(
        name="fallback_fake",
        model="fallback-model-v1",
        cost_input_per_million=0.5,
        cost_output_per_million=1.0,
        max_retries_on_429=2,
        backoff_initial_sec=0.01,
    )

    config = {
        "active_chain": ["primary_fake", "fallback_fake"],
        "providers": {
            "primary_fake": {
                "rate_limit": {"requests_per_minute": 60, "requests_per_day": 1000}
            },
            "fallback_fake": {
                "rate_limit": {"requests_per_minute": 60, "requests_per_day": 1000}
            },
        }
    }

    client = LLMClient(
        config=config,
        cache=cache,
        rate_limiter=rate_limiter,
        usage_logger=usage_logger,
        providers={"primary_fake": primary_provider, "fallback_fake": fallback_provider},
        active_chain=["primary_fake", "fallback_fake"],
        prompts_dir=sample_prompts_dir,
    )

    return {
        "client": client,
        "primary": primary_provider,
        "fallback": fallback_provider,
        "cache": cache,
        "usage_logger": usage_logger,
        "rate_limiter": rate_limiter,
        "job_queue": job_queue,
    }


def test_prompt_loader(sample_prompts_dir):
    """Test prompt loading, version header extraction, and variable interpolation."""
    tpl = load_prompt(
        "tag_question",
        {"stem": "What is Charyapada?", "options": ["Poetry", "Prose"], "taxonomy": "Bangla Lit"},
        prompts_dir=sample_prompts_dir
    )
    assert tpl.name == "tag_question"
    assert tpl.version == "1.2.0"
    assert tpl.system_prompt == "You are a classifier. Output JSON only."
    assert "What is Charyapada?" in tpl.rendered_text

    # Missing variable should raise ValueError
    with pytest.raises(ValueError, match="requires variable"):
        load_prompt("tag_question", {"stem": "Incomplete"}, prompts_dir=sample_prompts_dir)

    # Missing prompt file should raise PromptNotFoundError
    with pytest.raises(PromptNotFoundError):
        load_prompt("non_existent_prompt", {}, prompts_dir=sample_prompts_dir)


def test_complete_success_with_schema(llm_env):
    """Test successful completion and Pydantic validation."""
    client = llm_env["client"]
    primary = llm_env["primary"]
    usage_logger = llm_env["usage_logger"]

    expected_data = {
        "subject_code": "bangla",
        "topic_name": "প্রাচীন যুগ",
        "confidence": 0.98,
    }
    primary.set_responses([expected_data])

    result = client.complete(
        prompt_name="tag_question",
        variables={"stem": "চর্যাপদ কোন যুগের?", "options": ["প্রাচীন", "মধ্য"], "taxonomy": "বাংলা"},
        schema=QuestionTag,
        temperature=0.0,
    )

    assert isinstance(result, QuestionTag)
    assert result.subject_code == "bangla"
    assert result.confidence == 0.98

    # Verify usage logger recorded call
    summary = usage_logger.get_summary()
    assert summary["total_calls"] == 1
    assert summary["cache_hits"] == 0


def test_disk_cache_hits(llm_env):
    """Test that disk cache avoids external calls and records zero cost on hits."""
    client = llm_env["client"]
    primary = llm_env["primary"]
    usage_logger = llm_env["usage_logger"]

    data = {"subject_code": "bangla", "topic_name": "ব্যাকরণ", "confidence": 0.95}
    primary.set_responses([data])

    vars1 = {"stem": "সন্ধি কাকে বলে?", "options": ["ধ্বনি মিলন", "বর্ণ মিলন"], "taxonomy": "বাংলা"}

    # First call: cache miss, provider invoked
    res1 = client.complete("tag_question", vars1, QuestionTag)
    assert len(primary.call_history) == 1
    assert res1.topic_name == "ব্যাকরণ"

    # Second call with identical input: CACHE HIT (provider not called!)
    res2 = client.complete("tag_question", vars1, QuestionTag)
    assert len(primary.call_history) == 1  # Still 1! Provider was not invoked
    assert res2.topic_name == "ব্যাকরণ"

    # Verify summary shows 1 cache hit and 2 total calls
    summary = usage_logger.get_summary()
    assert summary["total_calls"] == 2
    assert summary["cache_hits"] == 1
    assert summary["cache_hit_rate"] == 0.5


def test_schema_validation_retry_once(llm_env):
    """Test that invalid JSON triggers a single retry with error feedback before succeeding."""
    client = llm_env["client"]
    primary = llm_env["primary"]

    invalid_first = "Invalid JSON string {"
    valid_second = {"subject_code": "english", "topic_name": "Idioms", "confidence": 0.88}

    primary.set_responses([invalid_first, valid_second])

    result = client.complete(
        prompt_name="tag_question",
        variables={"stem": "What is an idiom?", "options": ["Phrase", "Word"], "taxonomy": "English"},
        schema=QuestionTag,
    )

    assert result.subject_code == "english"
    assert len(primary.call_history) == 2

    # Second prompt must contain the error explanation to help the model correct itself
    retry_prompt = primary.call_history[1]["prompt"]
    assert "[CORRECTION REQUIRED]" in retry_prompt
    assert "JSON syntax error" in retry_prompt


def test_schema_validation_failure_after_retry(llm_env):
    """Test that repeated schema validation failures fail gracefully."""
    client = llm_env["client"]
    primary = llm_env["primary"]
    fallback = llm_env["fallback"]

    # Both primary and fallback return invalid schema
    primary.set_responses(["{bad json", "{still bad"])
    fallback.set_responses(["{worse", "{totally broken"])

    with pytest.raises(MaxRetriesExceededError):
        client.complete(
            prompt_name="tag_question",
            variables={"stem": "Question", "options": ["A", "B"], "taxonomy": "General"},
            schema=QuestionTag,
        )


def test_rate_limiter_and_provider_fallback(llm_env):
    """Test automatic fallback to next provider when primary is rate limited."""
    client = llm_env["client"]
    primary = llm_env["primary"]
    fallback = llm_env["fallback"]

    # Restrict primary provider to 1 request per minute
    client.config["providers"]["primary_fake"]["rate_limit"]["requests_per_minute"] = 1

    primary.set_responses([
        {"subject_code": "math", "topic_name": "Algebra", "confidence": 0.90},
    ])
    fallback.set_responses([
        {"subject_code": "math", "topic_name": "Geometry", "confidence": 0.91},
    ])

    # First call goes to primary
    vars1 = {"stem": "Find x", "options": ["1", "2"], "taxonomy": "Math"}
    res1 = client.complete("tag_question", vars1, QuestionTag)
    assert res1.topic_name == "Algebra"
    assert len(primary.call_history) == 1
    assert len(fallback.call_history) == 0

    # Second call (with different vars to bypass cache) hits primary rate limit -> falls back to fallback!
    vars2 = {"stem": "Find y", "options": ["3", "4"], "taxonomy": "Math"}
    res2 = client.complete("tag_question", vars2, QuestionTag)
    assert res2.topic_name == "Geometry"
    assert len(primary.call_history) == 1   # Primary was skipped due to rate limiter
    assert len(fallback.call_history) == 1  # Fallback took over!


def test_exponential_backoff_on_429(llm_env):
    """Test that HTTP 429 triggers exponential backoff retries before falling back."""
    client = llm_env["client"]
    primary = llm_env["primary"]
    fallback = llm_env["fallback"]

    # Primary raises RateLimitError on first call, then returns valid JSON
    primary.set_responses([
        RateLimitError("429 Too Many Requests"),
        {"subject_code": "ethics", "topic_name": "Values", "confidence": 0.95},
    ])

    res = client.complete(
        "tag_question",
        {"stem": "What is integrity?", "options": ["Honesty", "Power"], "taxonomy": "Ethics"},
        QuestionTag,
    )
    assert res.topic_name == "Values"
    assert len(primary.call_history) == 2


def test_job_queue_resumption(llm_env):
    """Test that batch job queue survives interruptions and resumes without duplicate work."""
    client = llm_env["client"]
    primary = llm_env["primary"]
    job_queue = llm_env["job_queue"]

    # Enqueue 3 batch items
    q_name = "batch_test_queue"
    job_ids = job_queue.enqueue_batch(
        queue_name=q_name,
        items=[
            {"prompt_name": "tag_question", "variables": {"stem": "Q1", "options": ["1", "2"], "taxonomy": "Tax"}},
            {"prompt_name": "tag_question", "variables": {"stem": "Q2", "options": ["1", "2"], "taxonomy": "Tax"}},
            {"prompt_name": "tag_question", "variables": {"stem": "Q3", "options": ["1", "2"], "taxonomy": "Tax"}},
        ]
    )
    assert len(job_ids) == 3

    # Primary responses
    primary.set_responses([
        {"subject_code": "sub1", "topic_name": "T1", "confidence": 0.9},
        {"subject_code": "sub2", "topic_name": "T2", "confidence": 0.9},
        {"subject_code": "sub3", "topic_name": "T3", "confidence": 0.9},
    ])

    # 1. Process only the first job manually
    job1 = job_queue.claim_next(q_name)
    assert job1 is not None
    res1 = client.complete(job1["prompt_name"], job1["variables"], QuestionTag)
    job_queue.complete(job1["job_id"], res1)

    stats1 = job_queue.get_stats(q_name)
    assert stats1["completed"] == 1
    assert stats1["pending"] == 2

    # 2. Simulate interruption: claim job 2, then simulate crash and call reset_stuck_jobs()
    job2 = job_queue.claim_next(q_name)
    assert job2["job_id"] == job_ids[1]
    # Crash happened here before completion!
    job_queue.reset_stuck_jobs(q_name)

    stats_after_crash = job_queue.get_stats(q_name)
    assert stats_after_crash["pending"] == 2  # Job 2 is safely back to pending!
    assert stats_after_crash["completed"] == 1

    # 3. Resume the queue with run_queue: should complete jobs 2 and 3 without repeating job 1
    final_stats = job_queue.run_queue(
        queue_name=q_name,
        complete_fn=client.complete,
        schema=QuestionTag,
    )

    assert final_stats["completed"] == 3
    assert final_stats["pending"] == 0
    assert final_stats["failed"] == 0
