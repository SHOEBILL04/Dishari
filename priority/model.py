"""Dirichlet-multinomial topic priority model with recency decay, shrinkage, and baselines."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import numpy as np
import pandas as pd
from scipy.stats import beta

from priority.dataset import (
    TOPIC_REGISTRY,
    TopicMeta,
    get_topics_dict,
    is_topic_active_in_syllabus,
    SUBJECT_MARKS_BY_SYLLABUS,
)


class PriorityTier(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class TopicPriorityPrediction:
    """Predicted distribution parameters and priority tier for a single topic."""
    topic_id: str
    subject_slug: str
    name_bn: str
    name_en: str
    posterior_mean_share: float
    ci_80_lower: float
    ci_80_upper: float
    expected_questions: float
    ci_80_questions_lower: float
    ci_80_questions_upper: float
    tier: PriorityTier


class DirichletMultinomialPriorityModel:
    """Dirichlet-Multinomial Bayesian model for topic share estimation.
    
    Features:
    - Exponential recency decay over past exams.
    - Bayesian shrinkage toward subject-wide mean share.
    - Syllabus change handling via active-exam exposure normalization.
    - Analytical 80% credible intervals via marginal Beta distribution.
    - News signal integration interface for Bangladesh & International Affairs.
    """

    def __init__(
        self,
        half_life: float = 3.0,
        shrinkage: float = 5.0,
        target_syllabus_version: str = "bcs-35th-current",
        news_weight: float = 0.5,
    ):
        """
        Args:
            half_life: Exam recency decay half-life t_{1/2}. (float('inf') for unweighted).
            shrinkage: Total Dirichlet prior pseudocount S toward the baseline share.
            target_syllabus_version: Target syllabus version to evaluate marks against.
            news_weight: Sensitivity weight for blending news signals when enabled.
        """
        self.half_life = half_life
        self.shrinkage = shrinkage
        self.target_syllabus_version = target_syllabus_version
        self.news_weight = news_weight
        self.topic_map = get_topics_dict()

    def _compute_recency_weight(self, exam_k: int, past_exam: int) -> float:
        """Compute exponential decay weight 2^{- (k - past_exam) / half_life}."""
        if np.isinf(self.half_life):
            return 1.0
        delta = max(0, exam_k - past_exam)
        return float(2.0 ** (-delta / self.half_life))

    def predict_subject(
        self,
        historical_df: pd.DataFrame,
        current_exam_k: int,
        subject_slug: str,
        news_signal: Optional[dict[str, float]] = None,
        news_enabled: bool = False,
        compute_ci: bool = True,
    ) -> list[TopicPriorityPrediction]:
        """Estimate topic shares and credible intervals for a subject.
        
        Args:
            historical_df: Historical counts dataframe up to exam k-1.
            current_exam_k: The exam being predicted (train on exams < current_exam_k).
            subject_slug: Target subject slug (e.g., 'bangla').
            news_signal: Optional dict mapping topic_id -> intensity score.
            news_enabled: Whether to apply the news signal (default False).
            compute_ci: Whether to compute 80% Beta credible intervals (set False during fast tuning).
        """
        # 1. Identify active topics for the target syllabus version
        active_topics = [
            t for t in TOPIC_REGISTRY
            if t.subject_slug == subject_slug and is_topic_active_in_syllabus(t, self.target_syllabus_version)
        ]
        if not active_topics:
            return []

        num_topics = len(active_topics)
        target_marks = float(
            SUBJECT_MARKS_BY_SYLLABUS.get(self.target_syllabus_version, {}).get(subject_slug, 10.0)
        )

        # Base prior: shrinkage toward subject-wide equal mean share (1 / num_topics)
        prior_mean_share = np.ones(num_topics, dtype=np.float64) / num_topics
        prior_alpha = self.shrinkage * prior_mean_share

        # 2. Filter historical data strictly to exams < current_exam_k
        train_df = historical_df[
            (historical_df["bcs_number"] < current_exam_k) &
            (historical_df["subject_slug"] == subject_slug)
        ]

        # 3. Calculate decayed observations with syllabus change handling
        decayed_counts = np.zeros(num_topics, dtype=np.float64)
        topic_counts: dict[str, list[tuple[int, float]]] = {}
        unique_past_exams = set()

        for row in train_df[["bcs_number", "topic_id", "question_count"]].itertuples(index=False):
            bcs_n = int(row.bcs_number)
            unique_past_exams.add(bcs_n)
            tid = str(row.topic_id)
            if tid not in topic_counts:
                topic_counts[tid] = []
            topic_counts[tid].append((bcs_n, float(row.question_count)))

        total_window_weight = sum(self._compute_recency_weight(current_exam_k, e) for e in unique_past_exams)

        for idx, t in enumerate(active_topics):
            topic_entries = topic_counts.get(t.topic_id)
            if not topic_entries:
                decayed_counts[idx] = 0.0
            else:
                active_weight = 0.0
                weighted_count = 0.0
                for bcs_n, count in topic_entries:
                    w = self._compute_recency_weight(current_exam_k, bcs_n)
                    active_weight += w
                    weighted_count += w * count

                if active_weight > 0:
                    active_rate = weighted_count / active_weight
                    decayed_counts[idx] = active_rate * (total_window_weight if total_window_weight > 0 else 1.0)
                else:
                    decayed_counts[idx] = 0.0

        # 4. Posterior Dirichlet parameters: alpha^* = alpha_0 + decayed_counts
        posterior_alpha = prior_alpha + decayed_counts

        # 5. Optional news signal tilt (Bangladesh & International Affairs only)
        if news_enabled and news_signal and subject_slug in ("bangladesh_affairs", "international_affairs"):
            for idx, t in enumerate(active_topics):
                score = max(0.0, float(news_signal.get(t.topic_id, 0.0)))
                posterior_alpha[idx] += self.news_weight * score

        alpha_sum = float(np.sum(posterior_alpha))
        posterior_mean_shares = posterior_alpha / alpha_sum

        # 6. Compute 80% credible interval via Beta marginals & expected questions
        predictions = []
        for idx, t in enumerate(active_topics):
            mean_share = float(posterior_mean_shares[idx])
            exp_q = float(target_marks * mean_share)

            if compute_ci:
                a = float(posterior_alpha[idx])
                b = float(alpha_sum - a)
                ci_lower = float(beta.ppf(0.10, a, b)) if a > 0 and b > 0 else 0.0
                ci_upper = float(beta.ppf(0.90, a, b)) if a > 0 and b > 0 else 1.0
            else:
                ci_lower = max(0.0, mean_share - 0.05)
                ci_upper = min(1.0, mean_share + 0.05)

            ci_q_lower = float(target_marks * ci_lower)
            ci_q_upper = float(target_marks * ci_upper)

            # Assign priority tier
            if exp_q >= 2.5 or mean_share >= (1.5 / num_topics):
                tier = PriorityTier.HIGH
            elif exp_q >= 1.0:
                tier = PriorityTier.MEDIUM
            else:
                tier = PriorityTier.LOW

            predictions.append(
                TopicPriorityPrediction(
                    topic_id=t.topic_id,
                    subject_slug=subject_slug,
                    name_bn=t.name_bn,
                    name_en=t.name_en,
                    posterior_mean_share=round(mean_share, 4),
                    ci_80_lower=round(ci_lower, 4),
                    ci_80_upper=round(ci_upper, 4),
                    expected_questions=round(exp_q, 2),
                    ci_80_questions_lower=round(ci_q_lower, 2),
                    ci_80_questions_upper=round(ci_q_upper, 2),
                    tier=tier,
                )
            )

        # Sort by expected questions descending
        predictions.sort(key=lambda p: p.expected_questions, reverse=True)
        return predictions

    def predict_all_subjects(
        self,
        historical_df: pd.DataFrame,
        current_exam_k: int,
        news_signal: Optional[dict[str, float]] = None,
        news_enabled: bool = False,
    ) -> dict[str, list[TopicPriorityPrediction]]:
        """Predict topic distributions for all subjects in the target syllabus."""
        results = {}
        sub_marks = SUBJECT_MARKS_BY_SYLLABUS.get(self.target_syllabus_version, {})
        for sub_slug in sub_marks.keys():
            results[sub_slug] = self.predict_subject(
                historical_df=historical_df,
                current_exam_k=current_exam_k,
                subject_slug=sub_slug,
                news_signal=news_signal,
                news_enabled=news_enabled,
            )
        return results


# ---------------------------------------------------------
# Baselines for Comparative Backtesting
# ---------------------------------------------------------

class UniformBaseline:
    """Baseline 1: Predicts equal topic share for all active topics within subject."""

    def __init__(self, target_syllabus_version: str = "bcs-35th-current"):
        self.target_syllabus_version = target_syllabus_version

    def predict_shares(self, subject_slug: str, current_exam_k: int, historical_df: pd.DataFrame) -> dict[str, float]:
        active_topics = [
            t for t in TOPIC_REGISTRY
            if t.subject_slug == subject_slug and is_topic_active_in_syllabus(t, self.target_syllabus_version)
        ]
        if not active_topics:
            return {}
        p = 1.0 / len(active_topics)
        return {t.topic_id: p for t in active_topics}


class AllTimeFrequencyBaseline:
    """Baseline 2: Unweighted all-time empirical frequency with Laplace smoothing."""

    def __init__(self, target_syllabus_version: str = "bcs-35th-current"):
        self.target_syllabus_version = target_syllabus_version

    def predict_shares(self, subject_slug: str, current_exam_k: int, historical_df: pd.DataFrame) -> dict[str, float]:
        active_topics = [
            t for t in TOPIC_REGISTRY
            if t.subject_slug == subject_slug and is_topic_active_in_syllabus(t, self.target_syllabus_version)
        ]
        if not active_topics:
            return {}

        train_df = historical_df[
            (historical_df["bcs_number"] < current_exam_k) &
            (historical_df["subject_slug"] == subject_slug)
        ]

        counts = {t.topic_id: 1.0 for t in active_topics}  # Laplace smoothing +1
        for _, r in train_df.iterrows():
            tid = r["topic_id"]
            if tid in counts:
                counts[tid] += float(r["question_count"])

        total = sum(counts.values())
        return {tid: c / total for tid, c in counts.items()}


class LastExamBaseline:
    """Baseline 3: Topic share from the immediate previous exam with Laplace smoothing."""

    def __init__(self, target_syllabus_version: str = "bcs-35th-current"):
        self.target_syllabus_version = target_syllabus_version

    def predict_shares(self, subject_slug: str, current_exam_k: int, historical_df: pd.DataFrame) -> dict[str, float]:
        active_topics = [
            t for t in TOPIC_REGISTRY
            if t.subject_slug == subject_slug and is_topic_active_in_syllabus(t, self.target_syllabus_version)
        ]
        if not active_topics:
            return {}

        prev_exams = historical_df[historical_df["bcs_number"] < current_exam_k]["bcs_number"]
        if prev_exams.empty:
            p = 1.0 / len(active_topics)
            return {t.topic_id: p for t in active_topics}

        last_exam = prev_exams.max()
        last_df = historical_df[
            (historical_df["bcs_number"] == last_exam) &
            (historical_df["subject_slug"] == subject_slug)
        ]

        counts = {t.topic_id: 1.0 for t in active_topics}  # Laplace smoothing +1
        for _, r in last_df.iterrows():
            tid = r["topic_id"]
            if tid in counts:
                counts[tid] += float(r["question_count"])

        total = sum(counts.values())
        return {tid: c / total for tid, c in counts.items()}
