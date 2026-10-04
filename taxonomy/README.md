# Taxonomy Module

## Purpose
Manages the hierarchical syllabus structure for the Bangladesh Civil Service (BCS) Preliminary Examination.

## Structure
- **Subject**: High-level area (e.g., Bangla, English, Bangladesh Affairs).
- **Topic**: Major syllabus branch (e.g., Bangla Literature, Medieval Period, Grammar - Sandhi).
- **Subtopic**: Granular concept tested in individual MCQs.

## Capabilities
- Supports multiple syllabus revisions (e.g., 35th+ BCS 200-mark syllabus vs legacy 100-mark syllabus).
- Hierarchical classification and tagging routines (connecting questions to topic IDs).
- Audit trail via `tag_log` table for model confidence and human verification.
