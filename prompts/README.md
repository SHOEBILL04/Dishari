# Prompts Module

## Purpose
This directory manages system prompts, few-shot prompt templates, and schema validation templates for all LLM-assisted workflows.

## Workflows Covered
1. **Classification & Tagging**: Prompts to map raw BCS questions to our hierarchical taxonomy.
2. **Question Generation**: Prompts conditioned on grounding reference passages to generate valid MCQs.
3. **Blind Verification**: Solvers tested on generated questions without seeing the answer key.
4. **Explanation Generation**: Clear, step-by-step explanations in Unicode Bangla.

## Guidelines
- All templates produce structured JSON output enforced via Pydantic or JSON schemas.
- Prompts must instruct models to use standard Unicode Bangla (NFC normalized).
