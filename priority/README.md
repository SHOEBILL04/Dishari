# Priority Module

## Purpose
Estimates topic importance and predicts which topics are likely to yield more questions in upcoming BCS exams.

## Architecture
- **Boundary**: Subject mark allocations (e.g., 35 for Bangla, 15 for Math) are fixed by the official BPSC circular and never altered by statistical models.
- **Inside-Subject Estimation**: Probabilistic models (frequency analysis, recency weighting, Poisson / Dirichlet-Multinomial regression) estimate expected question counts for specific subtopics *within* each subject.
- **Batch Processing**: Recalculated offline when new past papers are ingested.
