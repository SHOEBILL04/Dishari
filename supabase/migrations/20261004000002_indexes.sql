-- Migration: 002_indexes.sql
-- Description: Create indexes for foreign keys, common query filters, and vector similarity search.

-- 1. Foreign Key Performance Indexes
CREATE INDEX IF NOT EXISTS idx_syllabus_subject_marks_subject ON syllabus_subject_marks (subject_id);
CREATE INDEX IF NOT EXISTS idx_exams_syllabus_version ON exams (syllabus_version_id);
CREATE INDEX IF NOT EXISTS idx_topics_subject ON topics (subject_id);
CREATE INDEX IF NOT EXISTS idx_topics_parent ON topics (parent_id);
CREATE INDEX IF NOT EXISTS idx_topics_level ON topics (level);
CREATE INDEX IF NOT EXISTS idx_questions_exam ON questions (exam_id);
CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions (topic_id);
CREATE INDEX IF NOT EXISTS idx_questions_grounding_source ON questions (grounding_source_id);
CREATE INDEX IF NOT EXISTS idx_tag_log_question ON tag_log (question_id);
CREATE INDEX IF NOT EXISTS idx_tag_log_topic ON tag_log (topic_id);
CREATE INDEX IF NOT EXISTS idx_mocks_user ON mocks (user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts (user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_question ON attempts (question_id);
CREATE INDEX IF NOT EXISTS idx_attempts_mock ON attempts (mock_id);
CREATE INDEX IF NOT EXISTS idx_topic_mastery_topic ON topic_mastery (topic_id);
CREATE INDEX IF NOT EXISTS idx_review_cards_question ON review_cards (question_id);

-- 2. Query Filtering & Sorting Indexes
-- Exam paper lookup: ensure question numbers within an exam are unique and fast to look up
CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_exam_qno 
    ON questions (exam_id, q_no) 
    WHERE exam_id IS NOT NULL AND q_no IS NOT NULL;

-- Filter questions by status, source type, and topic for test assembly & review
CREATE INDEX IF NOT EXISTS idx_questions_status_topic 
    ON questions (status, topic_id);

CREATE INDEX IF NOT EXISTS idx_questions_source_type 
    ON questions (source_type);

-- Partial index for active/unexpired questions
CREATE INDEX IF NOT EXISTS idx_questions_active_expires 
    ON questions (expires_at) 
    WHERE expires_at IS NOT NULL;

-- Fast lookup for user attempt history sorted by time
CREATE INDEX IF NOT EXISTS idx_attempts_user_created 
    ON attempts (user_id, created_at DESC);

-- Fast lookup for due review flashcards
CREATE INDEX IF NOT EXISTS idx_review_cards_user_due 
    ON review_cards (user_id, due_at ASC);

CREATE INDEX IF NOT EXISTS idx_review_cards_user_state 
    ON review_cards (user_id, state);

-- 3. Vector Similarity Search Index (pgvector)
-- Using HNSW with cosine similarity for 384-dimensional sentence-transformers embeddings
CREATE INDEX IF NOT EXISTS idx_questions_embedding_hnsw 
    ON questions USING hnsw (embedding vector_cosine_ops);
