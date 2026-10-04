# Learner Module

## Purpose
Tracks candidate performance, models topic-level mastery, and powers personalized spaced repetition review schedules.

## Core Mechanisms
1. **Bayesian Topic Mastery**:
   - Uses a Beta-Binomial distribution per `(user_id, topic_id)` pair with parameters $\alpha$ (successes + prior) and $\beta$ (failures + prior).
   - Expected mastery = $\frac{\alpha}{\alpha + \beta}$.
   - Updates incrementally after each user attempt.
2. **Spaced Repetition Review (FSRS)**:
   - Synchronizes with client-side `ts-fsrs` parameters stored in `review_cards` table (`due_at`, `stability`, `difficulty`, `state`).
   - Surfaces items requiring timely review before memory decay.
