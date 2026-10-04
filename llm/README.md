# LLM Module (Provider-Agnostic Wrapper)

## Purpose
A robust, provider-agnostic interface for every language model call in Dishari. It protects against rate limits, API instability, provider downtime, and ensures structured JSON output conforming to strict Pydantic schemas.

---

## Core Interface

```python
from pydantic import BaseModel, Field
from llm import complete

class TagResult(BaseModel):
    subject_code: str
    topic_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)

# Load prompt /prompts/tag_question.md, format variables, validate schema
result: TagResult = complete(
    prompt_name="tag_question",
    variables={
        "stem": "চর্যাপদ কত সালে আবিষ্কৃত হয়?",
        "options": ["১৯০৫", "১৯০৭", "১৯১৬", "১৯২১"],
        "taxonomy_context": "বাংলা ভাষা ও সাহিত্য -> প্রাচীন যুগ"
    },
    schema=TagResult,
    temperature=0.0
)

print(result.subject_code, result.topic_name, result.confidence)
```

---

## Features & Implementation

### 1. Versioned Markdown Prompts (`/prompts/*.md`)
Prompts live in `/prompts` as markdown files with a YAML frontmatter header:
```markdown
---
version: 1.0.0
description: Tag BCS question to syllabus topic
system: |
  You are an expert exam classifier. Output strictly valid JSON matching the schema.
---
Question Stem:
{stem}

Options:
{options}
```
Every execution records the prompt version in the audit log table.

### 2. Provider Adapters (`config/llm.yaml`)
Providers are declared in `config/llm.yaml` with an active fallback chain:
```yaml
active_chain:
  - gemini
  - groq
  - openrouter
```
Adding a new provider is as simple as creating one small subclass of `BaseProvider` implementing:
```python
def generate(self, prompt: str, system_prompt: Optional[str] = None, 
             temperature: float = 0.0, schema: Optional[dict] = None) -> LLMResponse:
    ...
```

### 3. Disk Cache (SQLite)
- Responses are cached on disk (`data/llm_cache.sqlite`).
- Cache key is calculated deterministically:
  `SHA-256(prompt_name + prompt_version + json_variables + model + temperature)`.
- **Cache hits cost $0.00** and make zero external network requests.

### 4. Rate Limiting, Exponential Backoff & Automatic Fallback
- Tracks requests per minute (RPM) and requests per day (RPD) in SQLite.
- If HTTP 429 is encountered, applies exponential backoff with jitter up to `max_retries_on_429`.
- If rate limits are saturated or a provider is unreachable, execution automatically falls back to the next provider in the chain.

### 5. Strict Schema Validation & Self-Correction
- LLM output is validated against the specified Pydantic model.
- If JSON parsing fails or validation fails, the wrapper **retries once** with the exact error message appended to the prompt.
- If it fails again, the task is marked as failed.

### 6. Resumable Batch Job Queue (`JobQueue`)
Long-running offline batch jobs (e.g., tagging thousands of questions) use `JobQueue`:
```python
from llm import JobQueue, complete

queue = JobQueue("data/llm_jobs.sqlite")

# Add jobs in batch
queue.enqueue_batch("bcs_tagging", [
    {"prompt_name": "tag_question", "variables": {...}},
    ...
])

# Process with automatic resumption if interrupted
queue.run_queue("bcs_tagging", complete_fn=complete, schema=TagResult)
```
If the process is interrupted (Ctrl+C, crash), re-running the script picks up unfinished items without repeating completed ones.

### 7. Cost & Usage Logging Table
Every attempt (success, cache hit, retry, fallback, failure) is recorded in `data/llm_usage.sqlite` table `llm_usage_log`:
- `call_id`, `timestamp`, `prompt_name`, `prompt_version`, `provider`, `model`, `input_tokens`, `output_tokens`, `estimated_cost`, `latency_ms`, `cache_hit`, `status`, `error_message`.
