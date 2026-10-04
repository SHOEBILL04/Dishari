PROJECT: BCS Preliminary exam prep platform (Bangladesh Civil Service).

GOAL: (1) ingest past BCS preliminary MCQs, (2) tag them to a topic taxonomy,
(3) estimate which topics are likely to carry more questions in the next exam,
(4) generate verified similar MCQs, (5) assemble balanced 200-question mock tests,
(6) track each learner's weaknesses and schedule reviews.

EXAM FACTS (store in config, never hardcode in logic):
- 200 MCQs, 200 marks, 2 hours, 4 options per question.
- Subject marks change between exams (e.g. 43rd vs 50th BCS). Subject marks are
  known in advance from the circular; prediction only happens INSIDE each subject.
- Negative marking: read from config/exam_rules.yaml.

CONSTRAINTS:
- Near-zero budget. Heavy work runs offline in batch jobs, never per user request.
- Free-tier LLM limits are unstable: all LLM calls go through one provider-agnostic
  wrapper with caching, retries, rate limiting and JSON-schema validation.
- Bangla-first UI. All text is Unicode Bangla (NFC normalized). No Bijoy.
- LLMs are NOT a source of truth. Every generated question needs grounding passage,
  blind-solver verification, and a human-review queue.
- Do not scrape competitor sites. Use only sources I legitimately obtained.
- Personal/non-commercial use first; legal review before any monetization.

STACK: Python 3.11 for batch jobs (pandas, numpy, scikit-learn, sentence-transformers),
Postgres + pgvector (Supabase free tier), Next.js PWA frontend, ts-fsrs for review scheduling.

WORKING STYLE: small commits, tests for every module, README per module, type hints,
no secrets in code (use .env), idempotent batch scripts that can resume.