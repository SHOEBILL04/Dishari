-- Migration: 003_row_level_security.sql
-- Description: Configure Row-Level Security (RLS) policies for multi-tenant isolation and public catalog access.

-- 1. Enable RLS on all tables
ALTER TABLE syllabus_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE syllabus_subject_marks ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tag_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE mocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_mastery ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_cards ENABLE ROW LEVEL SECURITY;

-- 2. Public Read Policies for Curriculum & Reference Data
CREATE POLICY "Public read access for syllabus_versions" 
    ON syllabus_versions FOR SELECT 
    USING (true);

CREATE POLICY "Public read access for subjects" 
    ON subjects FOR SELECT 
    USING (true);

CREATE POLICY "Public read access for syllabus_subject_marks" 
    ON syllabus_subject_marks FOR SELECT 
    USING (true);

CREATE POLICY "Public read access for exams" 
    ON exams FOR SELECT 
    USING (true);

CREATE POLICY "Public read access for active topics" 
    ON topics FOR SELECT 
    USING (active = true);

CREATE POLICY "Public read access for sources" 
    ON sources FOR SELECT 
    USING (true);

-- Learners can only see verified questions that have not expired
CREATE POLICY "Public read access for verified questions" 
    ON questions FOR SELECT 
    USING (status = 'verified' AND (expires_at IS NULL OR expires_at > now()));

-- 3. User Data Isolation Policies (Auth UID scoped)
-- Users profile
CREATE POLICY "Users can view own profile" 
    ON users FOR SELECT 
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" 
    ON users FOR UPDATE 
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" 
    ON users FOR INSERT 
    WITH CHECK (auth.uid() = id);

-- Mocks
CREATE POLICY "Users can view own mocks" 
    ON mocks FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own mocks" 
    ON mocks FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

-- Attempts
CREATE POLICY "Users can view own attempts" 
    ON attempts FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own attempts" 
    ON attempts FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

-- Topic Mastery
CREATE POLICY "Users can view own topic mastery" 
    ON topic_mastery FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own topic mastery" 
    ON topic_mastery FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own topic mastery" 
    ON topic_mastery FOR UPDATE 
    USING (auth.uid() = user_id);

-- Review Cards (Spaced Repetition)
CREATE POLICY "Users can view own review cards" 
    ON review_cards FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own review cards" 
    ON review_cards FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own review cards" 
    ON review_cards FOR UPDATE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own review cards" 
    ON review_cards FOR DELETE 
    USING (auth.uid() = user_id);
