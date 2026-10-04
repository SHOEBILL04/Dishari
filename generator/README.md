# Generator Module

## Purpose
Generates high-quality, authentic BCS-style practice MCQs using LLMs grounded in verified reference materials.

## Safety & Quality Safeguards
- **Grounding Requirement**: LLMs are never treated as a source of truth. Every question generated must cite a specific reference source in the `sources` table.
- **Blind Solver Verification**: A secondary LLM agent solves the generated MCQ without viewing the proposed answer key. If it fails to find the exact intended answer, the question is flagged or discarded.
- **Human Review Queue**: Generated items enter the database as `status = 'draft'` or `status = 'needs_review'` until verified.
- **Expiration Tracking**: Current affairs questions specify an `expires_at` date to avoid obsolete information.
