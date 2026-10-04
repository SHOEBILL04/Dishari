-- Migration: 001_initial_schema.sql
-- Description: Create core schema, extensions, and domain tables for Dishari.

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Ensure auth schema exists for environments outside Supabase (e.g. local test runners)
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$ LANGUAGE sql STABLE;

-- 2. Syllabus Versions
CREATE TABLE IF NOT EXISTS syllabus_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    effective_from DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Subjects
CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) NOT NULL UNIQUE,
    name_bn VARCHAR(150) NOT NULL,
    name_en VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Syllabus Subject Marks
CREATE TABLE IF NOT EXISTS syllabus_subject_marks (
    syllabus_version_id UUID NOT NULL REFERENCES syllabus_versions(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    marks NUMERIC(5, 2) NOT NULL CHECK (marks > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (syllabus_version_id, subject_id)
);

-- 5. Exams
CREATE TABLE IF NOT EXISTS exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bcs_number INT NOT NULL UNIQUE CHECK (bcs_number > 0),
    year INT NOT NULL CHECK (year >= 1971),
    syllabus_version_id UUID NOT NULL REFERENCES syllabus_versions(id) ON DELETE RESTRICT,
    total_marks NUMERIC(5, 2) NOT NULL DEFAULT 200.00 CHECK (total_marks > 0),
    negative_mark NUMERIC(4, 3) NOT NULL DEFAULT 0.500 CHECK (negative_mark >= 0),
    duration_min INT NOT NULL DEFAULT 120 CHECK (duration_min > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Topics
CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    parent_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    name_bn VARCHAR(255) NOT NULL,
    name_en VARCHAR(255) NOT NULL,
    level INT NOT NULL DEFAULT 1 CHECK (level >= 1),
    syllabus_version_introduced UUID REFERENCES syllabus_versions(id) ON DELETE SET NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. Sources (Grounding materials)
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    url_or_citation TEXT NOT NULL,
    license_note TEXT,
    published_at TIMESTAMPTZ,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. Questions
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('past', 'generated')),
    exam_id UUID REFERENCES exams(id) ON DELETE SET NULL,
    q_no INT CHECK (q_no > 0),
    stem TEXT NOT NULL,
    options JSONB NOT NULL CHECK (jsonb_typeof(options) = 'array' AND jsonb_array_length(options) >= 2),
    correct_index INT NOT NULL CHECK (correct_index >= 0),
    explanation TEXT,
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    difficulty NUMERIC(4, 3) CHECK (difficulty >= 0.0 AND difficulty <= 1.0),
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'verified', 'rejected', 'needs_review')),
    grounding_source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. Tag Log (Classification & verification audit trail)
CREATE TABLE IF NOT EXISTS tag_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    model VARCHAR(100) NOT NULL,
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    confidence NUMERIC(5, 4) CHECK (confidence >= 0.0 AND confidence <= 1.0),
    reviewed_by_human BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. Mocks (Assembled full-length mock examinations)
CREATE TABLE IF NOT EXISTS mocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blueprint JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 12. Attempts (Question answering history)
CREATE TABLE IF NOT EXISTS attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    chosen_index INT,
    correct BOOLEAN NOT NULL,
    time_ms INT NOT NULL CHECK (time_ms >= 0),
    mock_id UUID REFERENCES mocks(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 13. Topic Mastery (Bayesian Beta-binomial model per user and topic)
CREATE TABLE IF NOT EXISTS topic_mastery (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    alpha NUMERIC(10, 4) NOT NULL DEFAULT 1.0000 CHECK (alpha > 0),
    beta NUMERIC(10, 4) NOT NULL DEFAULT 1.0000 CHECK (beta > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, topic_id)
);

-- 14. Review Cards (Spaced repetition schedule via ts-fsrs)
CREATE TABLE IF NOT EXISTS review_cards (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    due_at TIMESTAMPTZ NOT NULL,
    stability NUMERIC(10, 4) NOT NULL DEFAULT 0.0000 CHECK (stability >= 0),
    difficulty NUMERIC(10, 4) NOT NULL DEFAULT 0.0000 CHECK (difficulty >= 0 AND difficulty <= 10),
    state VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (state IN ('new', 'learning', 'review', 'relearning')),
    last_review TIMESTAMPTZ,
    reps INT NOT NULL DEFAULT 0 CHECK (reps >= 0),
    lapses INT NOT NULL DEFAULT 0 CHECK (lapses >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, question_id)
);
