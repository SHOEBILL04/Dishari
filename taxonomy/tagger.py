"""Topic tagging pipeline using kNN over labeled neighbors and LLM prompt B4 disambiguation."""

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from typing import Any, Optional, Sequence
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.neighbors import NearestNeighbors

from llm.client import complete, LLMClient
from taxonomy.embedder import QuestionEmbedder, get_embedder
from taxonomy.loader import format_candidate_topics_for_llm, get_all_topics_dict


class DisambiguationOutput(BaseModel):
    """Schema expected from LLM prompt B4."""
    topic_id: str = Field(..., description="Chosen candidate topic ID")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None


@dataclass
class TaggingResult:
    """Outcome of classifying a single question."""
    question_id: str
    predicted_topic_id: str
    confidence: float
    is_ambiguous: bool
    used_llm: bool
    candidate_topics: list[tuple[str, float]]  # (topic_id, similarity)
    needs_review: bool
    reasoning: Optional[str] = None


class TaxonomyTagger:
    """Classifier combining kNN candidate retrieval with LLM disambiguation for ambiguous edge cases."""

    def __init__(
        self,
        embedder: Optional[QuestionEmbedder] = None,
        llm_client: Optional[LLMClient] = None,
        k_neighbors: int = 5,
        ambiguity_margin: float = 0.08,
        min_similarity_threshold: float = 0.35,
        review_confidence_threshold: float = 0.80,
    ):
        self.embedder = embedder or get_embedder()
        self.llm_client = llm_client
        self.k_neighbors = k_neighbors
        self.ambiguity_margin = ambiguity_margin
        self.min_similarity_threshold = min_similarity_threshold
        self.review_confidence_threshold = review_confidence_threshold

        self.nn_model: Optional[NearestNeighbors] = None
        self.train_labels: list[str] = []
        self.train_embeddings: Optional[np.ndarray] = None
        self.train_df: Optional[pd.DataFrame] = None

    def fit(self, train_df: pd.DataFrame) -> None:
        """Fit kNN index on hand-labeled gold questions."""
        self.train_df = train_df.copy()
        self.train_labels = list(train_df["topic_id"])

        texts = []
        for _, row in train_df.iterrows():
            stem = str(row["stem"])
            opts = str(row.get("options", ""))
            texts.append(f"{stem} {opts}".strip())

        self.train_embeddings = self.embedder.embed_batch(texts, is_query=False)

        # Build NearestNeighbors model using cosine metric
        n_neighbors = min(self.k_neighbors, len(self.train_labels))
        self.nn_model = NearestNeighbors(
            n_neighbors=n_neighbors,
            metric="cosine",
            algorithm="brute",
        )
        self.nn_model.fit(self.train_embeddings)

    def get_knn_candidates(
        self,
        query_text: str,
        top_k: int = 5,
    ) -> tuple[list[tuple[str, float]], float]:
        """Query kNN index and return ranked candidate topics and agreement ratio.
        
        Returns:
            Tuple of (ranked_candidates: [(topic_id, similarity)], top1_agreement: float).
        """
        if self.nn_model is None or self.train_embeddings is None:
            raise RuntimeError("TaxonomyTagger must be fitted before predicting.")

        q_vec = np.array([self.embedder.embed_text(query_text, is_query=True)], dtype=np.float32)
        distances, indices = self.nn_model.kneighbors(q_vec)

        # Distances are cosine distances [0, 2]; similarity = 1 - distance
        topic_scores: dict[str, list[float]] = defaultdict(list)
        total_k = len(indices[0])

        for dist, idx in zip(distances[0], indices[0]):
            sim = max(0.0, 1.0 - float(dist))
            topic = self.train_labels[idx]
            topic_scores[topic].append(sim)

        # Aggregate candidate topic scores by mean similarity weighted by frequency
        aggregated = []
        for topic, sims in topic_scores.items():
            mean_sim = sum(sims) / len(sims)
            score = mean_sim * (1.0 + 0.1 * (len(sims) - 1))
            aggregated.append((topic, round(min(1.0, score), 4)))

        aggregated.sort(key=lambda x: x[1], reverse=True)
        top1_agreement = (len(topic_scores[aggregated[0][0]]) / total_k) if aggregated else 0.0

        return aggregated[:top_k], top1_agreement

    def is_ambiguous(self, candidates: list[tuple[str, float]]) -> bool:
        """Check whether the top candidates require LLM disambiguation."""
        if not candidates:
            return True

        # If all k neighbors unanimously belong to one topic, it is not ambiguous
        if len(candidates) == 1:
            return candidates[0][1] < self.min_similarity_threshold

        top1_sim = candidates[0][1]
        top2_sim = candidates[1][1]

        # Case 1: Overall top similarity is weak
        if top1_sim < self.min_similarity_threshold:
            return True

        # Case 2: Top-2 candidates are very close in score
        if (top1_sim - top2_sim) < self.ambiguity_margin:
            return True

        return False

    def predict_one(
        self,
        stem: str,
        options: Optional[Sequence[str]] = None,
        question_id: str = "q",
    ) -> TaggingResult:
        """Classify a single question using kNN and conditional LLM disambiguation."""
        opts_str = " ".join(options) if options else ""
        query_text = f"{stem} {opts_str}".strip()

        candidates, agreement = self.get_knn_candidates(query_text, top_k=5)
        if not candidates:
            return TaggingResult(
                question_id=question_id,
                predicted_topic_id="unknown",
                confidence=0.0,
                is_ambiguous=True,
                used_llm=False,
                candidate_topics=[],
                needs_review=True,
            )

        ambiguous = self.is_ambiguous(candidates)
        top1_topic, top1_sim = candidates[0]

        # Non-ambiguous case: high confidence directly from kNN
        if not ambiguous:
            # Confidence is derived from top similarity plus neighbor agreement bonus
            final_conf = min(0.99, round(top1_sim + (0.35 * agreement), 4))
            return TaggingResult(
                question_id=question_id,
                predicted_topic_id=top1_topic,
                confidence=final_conf,
                is_ambiguous=False,
                used_llm=False,
                candidate_topics=candidates,
                needs_review=(final_conf < self.review_confidence_threshold),
            )

        # Ambiguous case: call LLM with prompt B4 using top-5 candidates only
        top_ids = [c[0] for c in candidates]
        formatted_cands = format_candidate_topics_for_llm(top_ids)
        llm_success = False
        chosen_topic = top1_topic
        llm_conf = 0.5
        reasoning = None

        try:
            res: DisambiguationOutput = complete(
                prompt_name="b4_disambiguate_topic",
                variables={
                    "stem": stem,
                    "options": options or ["(ক)", "(খ)", "(গ)", "(ঘ)"],
                    "candidate_topics": formatted_cands,
                },
                schema=DisambiguationOutput,
                temperature=0.0,
                client=self.llm_client,
            )
            if res.topic_id in top_ids:
                chosen_topic = res.topic_id
                llm_conf = res.confidence
                reasoning = res.reasoning
                llm_success = True
        except Exception:
            # Fallback to kNN top-1 if LLM is unavailable
            llm_success = False

        # Final confidence combination:
        # 50% kNN similarity of the chosen topic + 50% LLM confidence
        chosen_sim = next((c[1] for c in candidates if c[0] == chosen_topic), top1_sim)
        if llm_success:
            final_conf = round((0.5 * chosen_sim) + (0.5 * llm_conf), 4)
        else:
            final_conf = round(chosen_sim * 0.85, 4)

        return TaggingResult(
            question_id=question_id,
            predicted_topic_id=chosen_topic,
            confidence=final_conf,
            is_ambiguous=True,
            used_llm=llm_success,
            candidate_topics=candidates,
            needs_review=(final_conf < self.review_confidence_threshold),
            reasoning=reasoning,
        )

    def evaluate(self, eval_df: pd.DataFrame) -> dict[str, Any]:
        """Evaluate accuracy and confusion on the gold evaluation set."""
        predictions = []
        confidences = []
        needs_review_count = 0
        used_llm_count = 0

        for _, row in eval_df.iterrows():
            stem = str(row["stem"])
            raw_opts = row.get("options", "")
            opts = json.loads(raw_opts) if isinstance(raw_opts, str) and raw_opts.startswith("[") else []
            res = self.predict_one(stem=stem, options=opts, question_id=str(row["id"]))
            predictions.append(res.predicted_topic_id)
            confidences.append(res.confidence)
            if res.needs_review:
                needs_review_count += 1
            if res.used_llm:
                used_llm_count += 1

        eval_df = eval_df.copy()
        eval_df["predicted_topic_id"] = predictions
        eval_df["confidence"] = confidences
        eval_df["correct"] = eval_df["topic_id"] == eval_df["predicted_topic_id"]

        overall_acc = float(eval_df["correct"].mean())

        # Per-subject accuracy & confusion
        subject_metrics: dict[str, dict[str, Any]] = {}
        confusion_pairs = Counter()

        for sub, sub_group in eval_df.groupby("subject_code"):
            sub_acc = float(sub_group["correct"].mean())
            subject_metrics[sub] = {
                "total": len(sub_group),
                "accuracy": round(sub_acc, 4),
            }

        # Find confused topic pairs
        for _, row in eval_df[~eval_df["correct"]].iterrows():
            true_t = row["topic_id"]
            pred_t = row["predicted_topic_id"]
            pair = f"{true_t} <-> {pred_t}"
            confusion_pairs[pair] += 1

        top_10_confused = confusion_pairs.most_common(10)

        report = {
            "overall_accuracy": round(overall_acc, 4),
            "target_reached": bool(overall_acc >= 0.90),
            "total_eval_samples": len(eval_df),
            "needs_review_queue_count": needs_review_count,
            "used_llm_count": used_llm_count,
            "subject_breakdown": subject_metrics,
            "top_10_confused_pairs": top_10_confused,
        }

        # Print report summary to stdout
        print("\n" + "="*50)
        print(f"TAXONOMY EVALUATION ON GOLD SET")
        print(f"Overall Accuracy: {overall_acc * 100:.2f}% (Target: >=90%)")
        print(f"Target Met: {'YES' if report['target_reached'] else 'NO'}")
        print(f"Items in Needs-Review Queue: {needs_review_count}/{len(eval_df)}")
        print("\nPer-Subject Accuracy Breakdown:")
        for sub, met in subject_metrics.items():
            print(f"  - {sub:22s}: {met['accuracy']*100:5.1f}% (n={met['total']})")

        print("\nTop 10 Most-Confused Topic Pairs:")
        if top_10_confused:
            for pair, count in top_10_confused:
                print(f"  - {pair}: {count} errors")
        else:
            print("  (None! Zero classification errors in evaluation set)")
        print("="*50 + "\n")

        if not report["target_reached"]:
            print("DIAGNOSTIC ADVICE TO REACH >=90% ACCURACY:")
            print("- Check the most-confused pairs above.")
            print("- Broaden or merge overlapping subtopics (e.g., related literature eras).")
            print("- Enrich topic keywords in taxonomy/bcs_topics.yaml for ambiguous domains.")

        return report


if __name__ == "__main__":
    from taxonomy.gold_set import load_and_split_gold_set
    print("Loading gold dataset and splitting into train/eval sets...")
    train_df, eval_df = load_and_split_gold_set()
    print(f"Loaded {len(train_df)} training samples and {len(eval_df)} evaluation samples.")
    tagger = TaxonomyTagger()
    print("Fitting kNN index on training set...")
    tagger.fit(train_df)
    print("Evaluating classifier on evaluation set...")
    tagger.evaluate(eval_df)
