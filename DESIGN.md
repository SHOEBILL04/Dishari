# Dishari Design Decisions (DESIGN.md)

This document explains the architecture and database design decisions for **Dishari**, an offline-first exam preparation platform for the Bangladesh Civil Service (BCS) Preliminary Examination.

---

## 1. Architectural Strategy

- **Zero-Budget Offline Batch Architecture**: Heavy computations—such as extracting text from past exam papers (OCR), classifying topics, generating questions, and computing embeddings—run as offline batch jobs using Python on a laptop or free GitHub Actions. The web application does not run heavy AI tasks when a user clicks a button.
- **Provider-Agnostic LLM Wrapper (`/llm`)**: Free-tier AI provider limits change frequently. All language model calls pass through a unified wrapper with request caching, retry logic, rate limit handling, and strict JSON output validation.
- **Bangla-First Unicode (NFC)**: All Bengali text is stored in standardized Unicode NFC format. Legacy Bijoy encoding is converted during ingestion to avoid search and display errors.
- **No Ground Truth in AI**: AI models can hallucinate. Therefore, every generated question must reference a verified text in the `sources` table and pass a blind test before reaching a candidate.

---

## 2. Directory Structure

| Directory | Purpose |
| :--- | :--- |
| `/config` | Exam rules, mark distributions, and syllabus settings. Exam rules are never hardcoded in application logic. |
| `/prompts` | Prompt templates for question tagging, generation, blind solving, and explanations. |
| `/ingest` | Scripts to extract questions from past BCS papers and clean Bengali text. |
| `/taxonomy` | Subject and topic hierarchy definitions and syllabus revision mapping. |
| `/priority` | Forecasting which topics inside each subject are likely to carry more questions. |
| `/generator` | Grounded question generation pipeline with blind solver verification. |
| `/assembler` | 200-question mock test assembler that strictly enforces subject mark quotas. |
| `/learner` | Bayesian topic mastery calculations and spaced repetition scheduling. |
| `/llm` | Provider-agnostic wrapper supporting Gemini, Groq, OpenRouter, and Ollama. |
| `/app` | Next.js Progressive Web App (PWA), static export for Cloudflare Pages. |
| `/tests` | Automated tests for database migrations, logic, and batch pipelines. |
| `/scripts` | Database migration runner, seed scripts, and maintenance tools. |
| `/data` | Raw documents and extracted datasets (gitignored to prevent repository bloat). |

---

## 3. Database Schema Decisions

The database is built on **PostgreSQL** with the **pgvector** extension. All primary keys use `UUID` (`gen_random_uuid()`) to prevent predictable ID guessing and to allow offline ID generation on client devices.

### 3.1 Syllabus & Exam Rules
- **`syllabus_versions` & `syllabus_subject_marks`**:
  - *Decision*: In BCS history, the exam format changed significantly (for example, the 35th BCS introduced the 200-mark syllabus, while earlier exams had 100 marks).
  - *Solution*: Marks per subject are stored in `syllabus_subject_marks` linked to `syllabus_versions`. This keeps past exam analysis accurate while allowing easy updates if future circulars change subject weights.
- **`exams`**:
  - *Decision*: Stores past official exams. `bcs_number` has a unique constraint (e.g., 43, 44, 45). Default values reflect standard BPSC rules: 200 marks, 0.5 negative mark deduction per wrong answer, and 120 minutes duration.

### 3.2 Subjects & Topic Taxonomy
- **`subjects`**:
  - Contains the 10 official BCS preliminary subjects with both Bengali (`name_bn`) and English (`name_en`) names.
- **`topics`**:
  - *Decision*: A single self-referencing table with `parent_id` and `level` (1 for major topic, 2 for subtopic, etc.).
  - *Why*: Avoids separate rigid tables for topics and subtopics. A tree structure easily accommodates fine-grained topics (e.g., *Bangla Literature* -> *Ancient Era* -> *Charyapada*).

### 3.3 Question Bank & Verification Lifecycle
- **`questions`**:
  - `source_type`: Distinguishes official past questions (`past`) from generated questions (`generated`).
  - `stem`: The question text in Unicode Bengali.
  - `options`: Stored as `JSONB` array (e.g., `["১৯০৫", "১৯০৭", "১৯১৬", "১৯২১"]`). This makes it easy to store 4 choices cleanly and validate length.
  - `correct_index`: 0-based integer pointing to the correct choice.
  - `difficulty`: A number between 0.00 and 1.00 based on test results.
  - `status`: Enforces question quality:
    - `draft`: Freshly parsed or generated.
    - `needs_review`: Flagged during verification or reported by users.
    - `verified`: Approved for candidate mock tests.
    - `rejected`: Discarded due to error or poor quality.
  - `grounding_source_id`: Foreign key to `sources`. Generated questions must link to a real source text to prevent hallucinations.
  - `expires_at`: Timestamp for time-sensitive current affairs questions, ensuring outdated facts are automatically retired.
  - `embedding`: A 384-dimensional vector (`vector(384)`) matching standard lightweight multilingual models (such as `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`).
- **`tag_log`**:
  - Stores which model or human tagged a question to a topic, with confidence score. Provides an audit trail for quality control.
- **`sources`**:
  - Stores background reading materials, reference texts, and citation details.

### 3.4 Candidate Learning & Spaced Repetition
- **`users`**:
  - Learner profile records linked to Supabase Auth (`auth.uid() = id`).
- **`attempts`**:
  - Logs every answer attempt: question ID, chosen option, boolean `correct`, time spent in milliseconds (`time_ms`), and optional `mock_id`.
- **`topic_mastery`**:
  - *Decision*: Tracks user strength on each topic using a **Beta-binomial model** ($\alpha, \beta$).
  - *Why*: Simple percentages (like 3/4 = 75%) fluctuate wildly after one question. Beta-binomial tracking starts with prior values ($\alpha=1, \beta=1$) and updates smoothly as the user answers more questions: $\text{Mastery} = \frac{\alpha}{\alpha + \beta}$.
- **`review_cards`**:
  - *Decision*: Stores spaced repetition flashcard parameters (`due_at`, `stability`, `difficulty`, `state`) compatible with the **ts-fsrs** (Free Spaced Repetition Scheduler) algorithm.
  - *Why*: The schedule runs directly in the candidate's browser without server roundtrips, and syncs back when online.
- **`mocks`**:
  - Stores full mock tests taken by users. The `blueprint` is stored as `JSONB` to capture the exact question list, random seed, and subject breakdown.

---

## 4. Indexing & Vector Search

1. **Foreign Key Indexes**: Every foreign key is indexed to keep joins and deletes fast.
2. **Composite Exam Question Index**: `CREATE UNIQUE INDEX idx_questions_exam_qno ON questions (exam_id, q_no) WHERE exam_id IS NOT NULL AND q_no IS NOT NULL;` ensures question numbers within a past paper cannot be duplicated.
3. **Partial Index for Active Questions**: An index on `expires_at` filters out expired current affairs quickly.
4. **HNSW Vector Index**:
   - `CREATE INDEX idx_questions_embedding_hnsw ON questions USING hnsw (embedding vector_cosine_ops);`
   - *Why HNSW over IVFFlat*: HNSW (Hierarchical Navigable Small World) provides high recall, does not require a minimum number of rows before building, and does not require periodic rebuilding as new questions are added.
   - Cosine distance (`vector_cosine_ops`) is used because sentence-transformer vectors are compared by angle of direction.

---

## 5. Security & Isolation (Row-Level Security)

Row-Level Security (RLS) is enabled on all tables:
- **Public Reference Data**: `syllabus_versions`, `subjects`, `syllabus_subject_marks`, `exams`, `topics`, `sources`, and verified questions (`status = 'verified' AND unexpired`) are readable by all users.
- **Private Candidate Data**: `users`, `attempts`, `topic_mastery`, `review_cards`, and `mocks` are strictly isolated using `auth.uid() = user_id`. Candidates can only view and update their own data.
- **Administrative Tasks**: Data ingestion, batch tagging, and question verification scripts use the Supabase `service_role` key, which securely bypasses RLS for batch operations.

---

## 6. Migration & Seed System

- **Migrations** live in `/migrations` and are mirrored in `/supabase/migrations`.
- **Runner (`scripts/migrate.py`)**: Reads SQL files in order, runs each inside a transaction, and records completed migrations in a `schema_migrations` table so they are never run twice.
- **Seed Script (`scripts/seed.sql`)**: Populates the 10 official subjects, standard 200-mark allocations for 35th+ BCS, past exams (43rd, 44th, 45th), starter topics, grounding sources, sample questions with embeddings, and a test candidate record.
- **Automated Tests (`tests/test_migrations.py`)**: Runs against a fresh, ephemeral PostgreSQL test container with `pgvector` to prove that migrations and seed data apply cleanly and remain completely idempotent.

---

## 7. LLM Provider Wrapper Architecture (`/llm`)

- **Interface**: `complete(prompt_name, variables, schema, temperature)` loads a markdown prompt, validates variables, queries models, and returns validated Pydantic objects or dictionaries.
- **Versioned Markdown Prompts**: Stored in `/prompts/*.md` with a YAML frontmatter header containing `version`, `description`, and `system`. Prompt version is logged on every call for auditing.
- **Provider Adapters & Fallback Chain**: Providers (Gemini, Groq, OpenRouter, Ollama) inherit from `BaseProvider`. The fallback chain (defined in `config/llm.yaml`) ensures that if a provider experiences downtime or rate limits, the next provider takes over automatically.
- **Disk Cache**: SQLite-backed (`llm_cache`). Key is `hash(prompt_name + prompt_version + variables + model + temperature)`. Cache hits make zero network calls and incur zero cost.
- **Rate Limiting & 429 Backoff**: Tracks requests per minute (RPM) and requests per day (RPD) in SQLite. On HTTP 429 status code, applies exponential backoff with jitter before falling back.
- **Strict Schema Validation & Single Self-Correction**: Parses and validates output against Pydantic models. On invalid JSON or schema errors, retries once with the error message appended to the prompt, helping the model self-correct.
- **Resumable Batch Job Queue (`JobQueue`)**: SQLite-backed queue (`llm_jobs`) that tracks pending, in-progress, completed, and failed tasks. If a batch script is interrupted by power loss or Ctrl+C, re-running the script resumes immediately without re-doing finished work.
- **Cost & Usage Logging**: Records token counts, estimated USD costs, latencies, cache hit status, and error messages in `llm_usage_log`.

