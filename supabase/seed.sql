-- Seed Data for Dishari BCS Prep Platform
-- Idempotent seed script inserting syllabus versions, subjects, marks, exams, topics, and initial questions.

BEGIN;

-- 1. Insert Syllabus Versions
INSERT INTO syllabus_versions (id, name, effective_from)
VALUES 
    ('00000000-0000-0000-0000-000000000001', '35th BCS to Present', '2014-01-01'),
    ('00000000-0000-0000-0000-000000000002', '10th to 34th BCS (Legacy)', '1989-01-01')
ON CONFLICT (id) DO UPDATE SET 
    name = EXCLUDED.name,
    effective_from = EXCLUDED.effective_from;

-- 2. Insert Subjects (Official 10 BCS Preliminary Subjects)
INSERT INTO subjects (id, slug, name_bn, name_en)
VALUES
    ('10000000-0000-0000-0000-000000000001', 'bangla', 'বাংলা ভাষা ও সাহিত্য', 'Bangla Language and Literature'),
    ('10000000-0000-0000-0000-000000000002', 'english', 'ইংরেজি ভাষা ও সাহিত্য', 'English Language and Literature'),
    ('10000000-0000-0000-0000-000000000003', 'bangladesh_affairs', 'বাংলাদেশ বিষয়াবলী', 'Bangladesh Affairs'),
    ('10000000-0000-0000-0000-000000000004', 'international_affairs', 'আন্তর্জাতিক বিষয়াবলী', 'International Affairs'),
    ('10000000-0000-0000-0000-000000000005', 'geography', 'ভূগোল (বাংলাদেশ ও বিশ্ব), পরিবেশ ও দুর্যোগ ব্যবস্থাপনা', 'Geography (Bangladesh & World), Environment and Disaster Management'),
    ('10000000-0000-0000-0000-000000000006', 'general_science', 'সাধারণ বিজ্ঞান', 'General Science'),
    ('10000000-0000-0000-0000-000000000007', 'computer_it', 'কম্পিউটার ও তথ্যপ্রযুক্তি', 'Computer and Information Technology'),
    ('10000000-0000-0000-0000-000000000008', 'math', 'গাণিতিক যুক্তি', 'Mathematical Reasoning'),
    ('10000000-0000-0000-0000-000000000009', 'mental_ability', 'মানসিক দক্ষতা', 'Mental Ability'),
    ('10000000-0000-0000-0000-000000000010', 'ethics', 'নৈতিকতা, মূল্যবোধ ও সুশাসন', 'Ethics, Values and Good Governance')
ON CONFLICT (id) DO UPDATE SET
    slug = EXCLUDED.slug,
    name_bn = EXCLUDED.name_bn,
    name_en = EXCLUDED.name_en;

-- 3. Insert Syllabus Subject Marks for "35th BCS to Present" (Total 200 Marks)
INSERT INTO syllabus_subject_marks (syllabus_version_id, subject_id, marks)
VALUES
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 35.00), -- Bangla
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002', 35.00), -- English
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000003', 30.00), -- Bangladesh Affairs
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000004', 20.00), -- International Affairs
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000005', 10.00), -- Geography
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000006', 15.00), -- General Science
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000007', 15.00), -- Computer & IT
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000008', 15.00), -- Math
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000009', 15.00), -- Mental Ability
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000010', 10.00)  -- Ethics
ON CONFLICT (syllabus_version_id, subject_id) DO UPDATE SET marks = EXCLUDED.marks;

-- 4. Insert Exams
INSERT INTO exams (id, bcs_number, year, syllabus_version_id, total_marks, negative_mark, duration_min)
VALUES
    ('20000000-0000-0000-0000-000000000043', 43, 2021, '00000000-0000-0000-0000-000000000001', 200.00, 0.500, 120),
    ('20000000-0000-0000-0000-000000000044', 44, 2022, '00000000-0000-0000-0000-000000000001', 200.00, 0.500, 120),
    ('20000000-0000-0000-0000-000000000045', 45, 2023, '00000000-0000-0000-0000-000000000001', 200.00, 0.500, 120)
ON CONFLICT (bcs_number) DO UPDATE SET
    year = EXCLUDED.year,
    syllabus_version_id = EXCLUDED.syllabus_version_id,
    total_marks = EXCLUDED.total_marks,
    negative_mark = EXCLUDED.negative_mark,
    duration_min = EXCLUDED.duration_min;

-- 5. Insert Core Topics
INSERT INTO topics (id, subject_id, parent_id, name_bn, name_en, level, syllabus_version_introduced, active)
VALUES
    -- Bangla Level 1
    ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', NULL, 'বাংলা ব্যাকরণ', 'Bangla Grammar', 1, '00000000-0000-0000-0000-000000000001', true),
    ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', NULL, 'বাংলা সাহিত্য', 'Bangla Literature', 1, '00000000-0000-0000-0000-000000000001', true),
    
    -- Bangla Level 2 Subtopics
    ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'ধ্বনি ও বর্ণ', 'Phonology & Alphabets', 2, '00000000-0000-0000-0000-000000000001', true),
    ('30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002', 'চর্যাপদ ও প্রাচীন যুগ', 'Charyapada & Ancient Era', 2, '00000000-0000-0000-0000-000000000001', true),

    -- English Level 1
    ('30000000-0000-0000-0000-000000000010', '10000000-0000-0000-0000-000000000002', NULL, 'English Grammar & Usage', 'English Grammar & Usage', 1, '00000000-0000-0000-0000-000000000001', true),
    ('30000000-0000-0000-0000-000000000011', '10000000-0000-0000-0000-000000000002', NULL, 'English Literature', 'English Literature', 1, '00000000-0000-0000-0000-000000000001', true),

    -- Bangladesh Affairs Level 1
    ('30000000-0000-0000-0000-000000000020', '10000000-0000-0000-0000-000000000003', NULL, 'মুক্তিযুদ্ধ ও স্বাধীনতা', 'Liberation War & Independence', 1, '00000000-0000-0000-0000-000000000001', true),
    ('30000000-0000-0000-0000-000000000021', '10000000-0000-0000-0000-000000000003', NULL, 'সংবিধান ও প্রশাসন', 'Constitution & Governance', 1, '00000000-0000-0000-0000-000000000001', true)
ON CONFLICT (id) DO UPDATE SET
    name_bn = EXCLUDED.name_bn,
    name_en = EXCLUDED.name_en,
    level = EXCLUDED.level,
    active = EXCLUDED.active;

-- 6. Insert Grounding Source
INSERT INTO sources (id, title, url_or_citation, license_note, published_at, text)
VALUES
    ('40000000-0000-0000-0000-000000000001', 
     'চর্যাপদ ভূমিকা ও ইতিহাস', 
     'হরপ্রসাদ শাস্ত্রী (১৯১৬), হাজার বছরের পুরাণ বাঙ্গালা ভাষায় রচিত বৌদ্ধ গান ও দোহা', 
     'Public domain historic reference material', 
     '1916-01-01', 
     'চর্যাপদ বাংলা সাহিত্যের প্রাচীনতম কাব্য তথা গান সংকলন। হরপ্রসাদ শাস্ত্রী ১৯০৭ সালে নেপালের রাজদরবারের রয়েল লাইব্রেরি থেকে এর পুঁথি আবিষ্কার করেন।')
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    text = EXCLUDED.text;

-- 7. Insert Sample Questions (with 384-dimensional zero vector placeholder for test seeding)
INSERT INTO questions (
    id, source_type, exam_id, q_no, stem, options, correct_index, explanation, 
    topic_id, difficulty, status, grounding_source_id, expires_at, embedding
)
VALUES
    (
        '50000000-0000-0000-0000-000000000001',
        'past',
        '20000000-0000-0000-0000-000000000043',
        1,
        'চর্যাপদ কত সালে আবিষ্কৃত হয়?',
        '["১৯০৫", "১৯০৭", "১৯১৬", "১৯২১"]'::jsonb,
        1,
        'মহামহোপাধ্যায় হরপ্রসাদ শাস্ত্রী ১৯০৭ সালে নেপালের রাজদরবারের রয়েল লাইব্রেরি থেকে চর্যাপদের মূল পুঁথি আবিষ্কার করেন এবং ১৯১৬ সালে বঙ্গীয় সাহিত্য পরিষদ থেকে তা প্রকাশ করেন।',
        '30000000-0000-0000-0000-000000000004',
        0.35,
        'verified',
        '40000000-0000-0000-0000-000000000001',
        NULL,
        array_fill(0.051::real, ARRAY[384])::vector(384)
    ),
    (
        '50000000-0000-0000-0000-000000000002',
        'past',
        '20000000-0000-0000-0000-000000000043',
        2,
        'বাংলাদেশের সংবিধান কার্যকর হয় কত তারিখে?',
        '["২৬ মার্চ ১৯৭২", "১৬ ডিসেম্বর ১৯৭২", "৪ নভেম্বর ১৯৭২", "১০ জানুয়ারি ১৯৭২"]'::jsonb,
        1,
        '১৯৭২ সালের ৪ নভেম্বর গণপরিষদে বাংলাদেশের সংবিধান গৃহীত হয় এবং একই বছরের ১৬ ডিসেম্বর অর্থাৎ প্রথম বিজয় দিবসে তা কার্যকর হয়।',
        '30000000-0000-0000-0000-000000000021',
        0.30,
        'verified',
        NULL,
        NULL,
        array_fill(0.051::real, ARRAY[384])::vector(384)
    )
ON CONFLICT (id) DO UPDATE SET
    stem = EXCLUDED.stem,
    options = EXCLUDED.options,
    correct_index = EXCLUDED.correct_index,
    status = EXCLUDED.status;

-- 8. Insert Tag Log for verification audit trail
INSERT INTO tag_log (id, question_id, model, topic_id, confidence, reviewed_by_human)
VALUES
    ('60000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 'seed_script', '30000000-0000-0000-0000-000000000004', 1.000, true),
    ('60000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000002', 'seed_script', '30000000-0000-0000-0000-000000000021', 1.000, true)
ON CONFLICT (id) DO NOTHING;

-- 9. Insert Sample User
INSERT INTO users (id, email, name)
VALUES
    ('70000000-0000-0000-0000-000000000001', 'candidate@dishari.app', 'BCS Candidate')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;

-- 10. Insert Mock Blueprint
INSERT INTO mocks (id, user_id, blueprint)
VALUES
    ('80000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '{"exam_type": "full_mock", "total_questions": 200, "syllabus_version": "35th BCS to Present"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- 11. Insert Sample Attempt
INSERT INTO attempts (id, user_id, question_id, chosen_index, correct, time_ms, mock_id)
VALUES
    ('90000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 1, true, 8500, '80000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

-- 12. Insert Topic Mastery
INSERT INTO topic_mastery (user_id, topic_id, alpha, beta, updated_at)
VALUES
    ('70000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000004', 2.0000, 1.0000, now())
ON CONFLICT (user_id, topic_id) DO UPDATE SET
    alpha = EXCLUDED.alpha,
    beta = EXCLUDED.beta,
    updated_at = EXCLUDED.updated_at;

-- 13. Insert Review Card (ts-fsrs state)
INSERT INTO review_cards (user_id, question_id, due_at, stability, difficulty, state, reps, lapses)
VALUES
    ('70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', now() + INTERVAL '1 day', 2.5000, 4.2000, 'learning', 1, 0)
ON CONFLICT (user_id, question_id) DO UPDATE SET
    due_at = EXCLUDED.due_at,
    stability = EXCLUDED.stability,
    difficulty = EXCLUDED.difficulty,
    state = EXCLUDED.state,
    updated_at = now();

COMMIT;
