# Ingest Module

## Purpose
The ingest module handles data extraction from past BCS preliminary question sources (PDFs or image scans named like `45_bcs_prelim.pdf`), runs multi-lingual OCR (Bengali and English), performs structure extraction, validates question integrity, flags anomalies, merges official answer keys, and provides a local Streamlit review tool before saving to PostgreSQL.

---

## Ingestion Pipeline Steps

### 1. 300 DPI Conversion, Deskew & Denoise (`preprocessor.py`)
- Renders each PDF page at **300 DPI** using `pypdfium2`.
- Converts pages to grayscale and detects skew angle using `cv2.minAreaRect`.
- Deskews the image around its center and applies bilateral denoising filters to smooth scan artifacts while keeping text sharp.

### 2. Multi-lingual OCR with Line Confidences (`ocr.py`)
- Executes **Tesseract OCR (ben+eng)** with language files in `data/tessdata/`.
- Computes per-line text and word confidence scores, along with an overall page mean confidence.
- Normalizes all Bengali text to standardized **Unicode NFC**.

### 3. Vision LLM Fallback (`prompts/b1_vision_ocr.md`)
- If page mean confidence falls below the threshold (default 60%), the page image is sent to a vision-capable LLM using prompt **B1**.
- **Both outputs are preserved** (`tesseract_text` and `vision_text`) for auditing and debugging.

### 4. Structured Question Extraction & Validation (`parser.py`)
- Extracts structured question records using prompt **B2** (`prompts/b2_extract_questions.md`) with a deterministic regex fallback.
- **Validations & Anomaly Flags**:
  - Exactly 4 options per question (`len(options) == 4`). Questions with fewer or more options are flagged as `invalid_options_count`.
  - Question numbers must be contiguous (e.g. 1, 2, 3...). Gaps are flagged as `missing_questions`.
  - Total question count is validated against official exam rules in `config/exam_rules.yaml` (200 for 35th+ BCS, 100 for legacy). Count mismatches are logged.

### 5. Official Answer Keys (`answer_keys.py`)
- Answer keys are loaded directly from an official CSV file (e.g. `q_no,answer`).
- Supports options formatted as numbers (0..3 or 1..4), Bengali letters (ক, খ, গ, ঘ), or English letters (A, B, C, D).
- **Rule**: LLMs are **never** used to guess or infer official answer keys. If no official key is provided, `correct_index` remains `null`.

### 6. Semantic Deduplication (`dedupe.py`)
- Generates 384-dimensional vector embeddings for question stems.
- Computes cosine similarity across all questions in the current batch and past exams.
- **Threshold**: Questions with cosine similarity **> 0.92** are flagged as `possible_duplicate`.
- **Rule**: Questions are **never auto-deleted**. They are flagged for human review.

### 7. Per-Exam Ingestion Report (`pipeline.py`)
Produces a structured report saved to `data/ingest/{bcs_number}_bcs/report.json`:
- Questions parsed
- Questions flagged (with breakdown of flags: low OCR confidence, invalid options count, duplicates, gaps)
- Questions approved
- Anomalies list

---

## Local Review Tool (Streamlit)

A local web application displays source images beside parsed questions for verification:

```bash
# Launch review app
streamlit run ingest/review_app.py
```

### Features:
- **Side-by-Side Review**: Original high-resolution page image is displayed directly beside the extracted question fields.
- **Editable Fields**: Edit stem, 4 options, official answer key index, explanation, and topic assignment.
- **Flag Alerts**: Visually highlights flagged anomalies (e.g., duplicate warnings, missing options).
- **Approve Button**: Sets `approved = True` and `status = 'verified'`.
- **Postgres Database Insertion**: Clicking **"Insert Approved Questions to PostgreSQL"** inserts **only approved questions** into the database with `source_type = 'past'`. Unapproved items remain safely in the staging queue.
