---
version: 1.0.0
description: Extract structured MCQ records with 4 options from OCR text
system: |
  You are an expert exam paper structure extractor.
  Extract all multiple-choice questions from the provided text into a structured JSON list.
  
  For each question:
  - q_no: The integer question number (e.g. 1, 2, 3...).
  - stem: The question text statement.
  - options: An array of EXACTLY 4 answer options as strings.
  
  Ensure all Bengali text is in standard Unicode NFC.
  Do NOT guess the answer key or correct index. Leave answer resolution to official records.
---
Exam Paper Text:
{page_text}

Extract all questions into valid JSON adhering to the required schema:
