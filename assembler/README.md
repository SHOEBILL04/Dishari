# Assembler Module

## Purpose
Assembles balanced, authentic 200-question full-length mock examinations that closely simulate the real BCS Preliminary Examination.

## Constraints Enforced
1. **Total Marks & Count**: Exactly 200 questions, 1 mark each.
2. **Subject Quotas**: Strict conformity with official subject marks (e.g., 35 Bangla, 35 English, 30 Bangladesh Affairs, etc.) from `config/exam_rules.yaml`.
3. **Topic & Subtopic Balance**: Even distribution across subtopics informed by priority scores.
4. **Difficulty Balance**: Balanced distribution between easy, medium, and challenging items.
5. **Blueprint Recording**: Full generation blueprint serialized as JSONB in the `mocks` table for repeatable review and scoring.
