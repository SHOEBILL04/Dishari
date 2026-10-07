# Prompts Module

## Purpose
This directory manages system prompts, few-shot prompt templates, and schema validation templates for all LLM-assisted workflows.

## Workflows Covered
1. **Classification & Tagging**: Prompts to map raw BCS questions to our hierarchical taxonomy.
2. **Question Generation**: Prompts conditioned on grounding reference passages to generate valid MCQs.
3. **Blind Verification**: Solvers tested on generated questions without seeing the answer key.
4. **Explanation Generation**: Clear, step-by-step explanations in Unicode Bangla.

## Current Prompt Inventory

| Identifier | File | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **B1** | `b1_vision_ocr.md` | `1.0.0` | Vision-capable LLM OCR extraction for degraded scanned exam pages. |
| **B2** | `b2_extract_questions.md` | `1.0.0` | Structured extraction of questions, options, and numbers into JSON. |
| **B3** | `b3_draft_taxonomy.md` | `1.0.0` | Drafting hierarchical BCS syllabus taxonomy trees versioned by syllabus. |
| **B4** | `b4_disambiguate_topic.md` | `1.0.0` | Disambiguating question topic classification from top-5 candidates. |

## Guidelines
- All templates produce structured JSON output enforced via Pydantic or JSON schemas.
- Prompts must instruct models to use standard Unicode Bangla (NFC normalized).
