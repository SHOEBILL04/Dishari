# App Module (Next.js PWA Frontend)

## Purpose
The frontend user interface for Dishari, designed as an installable Progressive Web Application (PWA).

## Architectural Principles
- **Static Export**: Generates static HTML/JS/CSS assets ready for Cloudflare Pages global distribution without a Node.js server.
- **Bangla-First**: Designed natively in Unicode Bangla (NFC normalized) with clear typography.
- **Offline Capable**: Candidates can take mock exams and review flashcards offline; results sync automatically when network connectivity is restored.
- **Client-Side Spaced Repetition**: Utilizes `ts-fsrs` directly on client devices for instant review scheduling.
- **Auth & RLS**: Directly communicates with Supabase Auth and database via Row-Level Security (RLS).
