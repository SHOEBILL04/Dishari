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

---

## 8. Ingest Pipeline Architecture (`/ingest`)

- **High-Resolution Preprocessing**: PDF pages are rendered at 300 DPI to ensure clear Bengali letterforms. OpenCV automatically computes skew angles using text bounding boxes and deskews rotated pages. Bilateral denoising cleans scan noise without blurring thin Bengali diacritics.
- **Tesseract ben+eng with Line Confidence**: Runs multi-lingual OCR and collects word and line-level confidence scores. The page mean confidence provides an objective measure of OCR clarity.
- **Vision LLM Fallback (Prompt B1)**: For low-confidence pages (< 60%), the image is submitted to a vision-capable LLM using prompt B1. Both the Tesseract text and Vision LLM text are saved so human reviewers can compare both.
- **Structured Extraction (Prompt B2) & Anomaly Flagging**: Prompts extract question stem, options, and question numbers into structured JSON records. Anomaly checks enforce:
  1. Exactly 4 options per question.
  2. Sequential question numbering without gaps.
  3. Total question count matching official exam rules in `config/exam_rules.yaml`.
- **Zero-Guesswork Official Answer Keys**: Answer keys are imported strictly from official CSV spreadsheets. The system **never uses an LLM to guess answer keys**. Questions without official keys leave `correct_index` as null.
- **Embedding Deduplication**: Vector cosine similarity > 0.92 flags possible duplicates across exams. Suspected duplicates are **never automatically deleted**; they are flagged for human review.
- **Streamlit Review Studio**: A local web interface presents the original page image directly beside the parsed question with editable fields and anomaly warnings. Only questions explicitly approved by a human reviewer are saved to the PostgreSQL database as `source_type = 'past'`.

---

## 9. Taxonomy & Topic Classification Architecture (`/taxonomy`)

### 9.1 Versioned Syllabus Hierarchy
- **File**: `taxonomy/bcs_topics.yaml` drafted using **Prompt B3** (`prompts/b3_draft_taxonomy.md`).
- **Rationale**: The BPSC syllabus changes over time (for example, the transition from the legacy 100-mark syllabus to the modern 200-mark syllabus with the 35th BCS). Structuring the YAML under top-level keys (`syllabus_versions: bcs-35th-current: ...`) enables retroactive tagging of older papers without distorting current mark distribution algorithms.
- **Bi-lingual Identification**: Every node contains `name_bn` (primary candidate interface) and `name_en` (administrative logging), paired with domain-specific keywords for semantic retrieval.

### 9.2 Embedding Strategy & Model Selection
- **Default Model**: `intfloat/multilingual-e5-small` producing 384-dimensional dense vectors.
- **Asymmetric Prefix Invariant**: The E5 model family is trained with contrastive asymmetric objective functions. Passing plain strings degrades retrieval precision by up to 10-15%. Therefore, `QuestionEmbedder` enforces:
  - `"query: "` prefix for incoming unclassified question stems and options.
  - `"passage: "` prefix for reference syllabus topics and gold question clusters.
- **Offline Deterministic Fallback**: In restricted offline testing environments lacking PyTorch/HuggingFace libraries, the system falls back to an L2-normalized 384-dimensional character-n-gram vectorizer, ensuring zero downtime and fully deterministic continuous integration tests.

### 9.3 Two-Stage Hybrid Tagging Pipeline
Running every question through an LLM is slow, expensive, and unnecessary when 80%+ of questions clearly belong to dense topic clusters. Conversely, relying purely on kNN nearest neighbors leads to systematic failure on ambiguous boundary cases (e.g., distinguishing *Bangla Medieval Literature* from *Ancient Era*, or *Parts of Speech* from *Clause Analysis*).

The hybrid architecture resolves this through four stages:
1. **kNN Neighborhood Search ($k=5$)**: Locates the 5 nearest labeled questions from `data/gold.csv` using cosine distance ($1 - \text{cosine\_distance}$).
2. **Ambiguity Gate**:
   - A question is flagged as **ambiguous** if:
     - The top neighbor's cosine similarity is below the minimum threshold ($\text{sim}_1 < 0.35$).
     - The similarity gap between candidate 1 and candidate 2 is small ($(\text{sim}_1 - \text{sim}_2) < 0.08$).
3. **Targeted LLM Disambiguation (Prompt B4)**:
   - For ambiguous cases only, Prompt B4 is invoked via `/llm` with the **top-5 candidate topics only**.
   - Giving the LLM the top 5 candidates prevents open-ended hallucination and bounds context length to $< 400$ tokens.
4. **Human Review Queue (`needs_review`)**:
   - Any question whose final confidence falls below $0.80$ is routed to the local review queue.

### 9.4 Final Confidence Formula & Mathematical Justification

The confidence score must accurately reflect true predictive certainty to prevent unverified topics from skewing spaced repetition intervals and mock test assemblers. We justify the two operational branches as follows:

#### Branch A: Unambiguous kNN Prediction
$$\text{Confidence}_{\text{kNN}} = \min\left(0.99, \text{sim}_1 + 0.35 \times \text{Agreement}\right)$$
Where:
- $\text{sim}_1$ is the cosine similarity score of the top-matching candidate ($0.0 \le \text{sim}_1 \le 1.0$).
- $\text{Agreement} = \frac{\text{count}(top\_1 \text{ among } k \text{ neighbors})}{k}$.
- **Justification**: Cosine similarity measures geometric angle to the nearest single neighbor, but does not capture local neighborhood density. Adding $+0.35 \times \text{Agreement}$ rewards cluster consensus. For instance, if all 5 neighbors belong to `top_bn_gram_sandhi` ($\text{Agreement} = 1.0$) with $\text{sim}_1 = 0.65$, the final confidence reaches $\min(0.99, 0.65 + 0.35) = 0.99$. If the neighborhood is split, the score remains unboosted and naturally flags for review if below $0.80$.

#### Branch B: Ambiguous Cases Disambiguated by LLM (Prompt B4)
$$\text{Confidence}_{\text{hybrid}} = 0.5 \times \text{sim}_{\text{kNN}}(\text{chosen\_topic}) + 0.5 \times \text{Confidence}_{\text{LLM}}$$
Where:
- $\text{sim}_{\text{kNN}}(\text{chosen\_topic})$ is the vector similarity of the candidate chosen by the LLM.
- $\text{Confidence}_{\text{LLM}}$ is the model's calibrated confidence output ($0.0 \le \text{Confidence}_{\text{LLM}} \le 1.0$).
- **Justification**: Giving 50% weight to vector similarity and 50% to LLM semantic reasoning ensures both geometric proximity and linguistic understanding agree before achieving high confidence. If an LLM selects a topic with $0.90$ confidence but vector similarity is only $0.40$, the hybrid score is $0.5(0.40) + 0.5(0.90) = 0.65$, correctly routing the question to human review ($< 0.80$).
- **Fallback Rule**: If the LLM provider is offline or rate-limited during an ambiguous case, the tagger assigns $\text{Confidence} = \text{sim}_1 \times 0.85$, applying a mandatory 15% ambiguity penalty that safely redirects the item to human review.

### 9.5 Needs-Review UI with Keyboard Shortcuts
- Located in `taxonomy/review_ui.py`.
- Features single-key navigation (`1`-`5` for candidates, `A`/`Enter` to approve, `N` to skip).
- Directly updates the PostgreSQL `questions.topic_id` and writes an audit record to `tag_log(reviewed_by_human = true)`.


