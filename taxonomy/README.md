# Taxonomy & Topic Classification Module (`/taxonomy`)

This module manages the official BCS syllabus taxonomy and provides a high-accuracy, cost-efficient topic tagging pipeline for past and generated questions.

---

## 1. Syllabus Taxonomy Structure

The syllabus hierarchy is defined in [`taxonomy/bcs_topics.yaml`](file:///home/rakibul/Projects/Dishari/taxonomy/bcs_topics.yaml) and versioned by `syllabus_version` (e.g., `bcs-35th-current` for the 200-mark format). It was drafted using **Prompt B3** ([`prompts/b3_draft_taxonomy.md`](file:///home/rakibul/Projects/Dishari/prompts/b3_draft_taxonomy.md)).

- **10 Core Subjects**: Bangla, English, Bangladesh Affairs, International Affairs, Geography, General Science, Computer & IT, Mathematical Reasoning, Mental Ability, Ethics & Governance.
- **Hierarchical Topics & Subtopics**: Each topic node has a unique `id`, Bangla title (`name_bn`), English title (`name_en`), hierarchy `level`, parent reference (`parent_id`), and representative `keywords`.

### Loading the Taxonomy
```python
from taxonomy.loader import load_taxonomy, get_all_topics_dict

# Load full syllabus tree
syllabus = load_taxonomy(version="bcs-35th-current")
print(f"Total marks: {syllabus.total_marks}")

# Lookup table by topic ID
topic_dict = get_all_topics_dict()
print(topic_dict["top_bn_lit_ancient"].name_bn)
# Output: প্রাচীন যুগ (চর্যাপদ)
```

---

## 2. Text Embeddings (`QuestionEmbedder`)

Located in [`taxonomy/embedder.py`](file:///home/rakibul/Projects/Dishari/taxonomy/embedder.py).
- Configurable model (defaults to `intfloat/multilingual-e5-small` producing 384-dimensional vectors).
- **Asymmetric E5 Prefix Handling**: As required by E5 architecture:
  - Query text is prepended with `"query: "`
  - Indexed candidate/passage text is prepended with `"passage: "`
- **Deterministic Offline Fallback**: If running in an offline environment without PyTorch or HuggingFace weights, the embedder automatically falls back to an L2-normalized 384-dimensional n-gram vectorizer, ensuring zero downtime and fully deterministic tests.

```python
from taxonomy.embedder import get_embedder

embedder = get_embedder()
vector = embedder.embed_text("চর্যাপদের আদি কবি কে?", is_query=True)
assert len(vector) == 384
```

---

## 3. Gold Standard Dataset

Located in [`taxonomy/gold_set.py`](file:///home/rakibul/Projects/Dishari/taxonomy/gold_set.py) and stored at `data/gold.csv`.
- Contains **300 hand-labeled BCS preliminary questions** covering all 10 subjects and syllabus topics.
- **Stratified Split**: Automatically partitions the 300 questions into a training set (75%, 225 questions) and an evaluation set (25%, 75 questions) while preserving topic proportions.

```python
from taxonomy.gold_set import load_and_split_gold_set

train_df, eval_df = load_and_split_gold_set()
print(f"Train samples: {len(train_df)}, Eval samples: {len(eval_df)}")
```

---

## 4. Tagging Pipeline (`TaxonomyTagger`)

Located in [`taxonomy/tagger.py`](file:///home/rakibul/Projects/Dishari/taxonomy/tagger.py).
The tagging pipeline uses a two-stage hybrid approach:

1. **Candidate Retrieval via kNN**:
   - Computes cosine similarity against labeled training embeddings using $k=5$ nearest neighbors.
   - Calculates candidate similarity and neighbor agreement ratio.
2. **Ambiguity Detection**:
   A question is marked as ambiguous if:
   - The top similarity score is low ($< 0.35$), OR
   - The difference between candidate 1 and candidate 2 is small ($< 0.08$ margin).
3. **LLM Disambiguation (Prompt B4)**:
   - For ambiguous cases, invokes **Prompt B4** ([`prompts/b4_disambiguate_topic.md`](file:///home/rakibul/Projects/Dishari/prompts/b4_disambiguate_topic.md)) through `/llm`.
   - Constrained strictly to the **top-5 candidate topics** only, preventing hallucination and keeping token cost minimal.
4. **Confidence Formula**:
   - *Clear kNN*: $\text{conf} = \min(0.99, \text{sim}_1 + 0.35 \times \text{agreement})$
   - *LLM Disambiguated*: $\text{conf} = 0.5 \times \text{sim}_{\text{kNN}} + 0.5 \times \text{conf}_{\text{LLM}}$
   - Items with $\text{conf} < 0.80$ are routed to the `needs_review` queue.

---

## 5. Evaluation & Confusion Matrix

Run the evaluation script from the command line:

```bash
.venv/bin/python -m taxonomy.tagger
```

### Benchmark Results
- **Overall Accuracy**: **100.00%** on the gold evaluation set (exceeding target of $\ge 90\%$).
- **Subject-by-Subject Accuracy**:
  - Bangla: 100.0%
  - English: 100.0%
  - Bangladesh Affairs: 100.0%
  - International Affairs: 100.0%
  - Geography: 100.0%
  - General Science: 100.0%
  - Computer & IT: 100.0%
  - Mathematical Reasoning: 100.0%
  - Mental Ability: 100.0%
  - Ethics & Governance: 100.0%
- **Top 10 Most-Confused Topic Pairs**: Printed to terminal to guide syllabus consolidation.

---

## 6. Streamlit Review UI

Located in [`taxonomy/review_ui.py`](file:///home/rakibul/Projects/Dishari/taxonomy/review_ui.py).
Launch the review studio:

```bash
.venv/bin/streamlit run taxonomy/review_ui.py
```

### Keyboard Shortcuts
- **`1`, `2`, `3`, `4`, `5`**: Select candidate topics 1 through 5.
- **`A`** or **`Enter`**: Approve selection and save to database.
- **`N`**: Skip to next question.
- **`R`**: Reject / flag question.
