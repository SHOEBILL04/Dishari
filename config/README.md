# Config Module

## Purpose
This directory stores all static configuration, exam rules, subject weight distributions, syllabus specifications, and environment settings.

## Rules
- **No Hardcoding**: Exam facts (such as question counts, mark values, time limits, and negative marking ratios) must never be written directly into Python or TypeScript application logic. They must be loaded dynamically from `exam_rules.yaml`.
- **Syllabus Versioning**: Subject marks change between syllabus eras (e.g., 34th BCS vs 35th+ BCS). Syllabus definitions here map the ground truth circulars.
- **Environment**: Secrets and environment-specific credentials are kept in `.env` (templated in `.env.example`).
