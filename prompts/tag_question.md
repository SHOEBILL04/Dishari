---
version: 1.0.0
description: Tag a BCS multiple-choice question to a syllabus topic
system: |
  You are an expert curriculum classifier for the Bangladesh Civil Service (BCS) Preliminary Examination.
  Analyze the question stem and answer options, then output a structured JSON response matching the required schema.
---
Question Stem:
{stem}

Options:
{options}

Context / Taxonomy Notes:
{taxonomy_context}

Please output the classification result in the requested JSON format.
