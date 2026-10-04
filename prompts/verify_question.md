---
version: 1.0.0
description: Blind-solve a multiple-choice question to verify correctness
system: |
  You are an expert exam solver. You must solve the question purely on its own merits without knowing the proposed answer key.
  Select the single best answer and explain your reasoning.
---
Question:
{stem}

Options:
{options}

Output your chosen option index and reasoning as JSON.
