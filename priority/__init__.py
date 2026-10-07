"""Priority package for Dirichlet-multinomial topic share estimation and exam backtesting."""

from priority.dataset import (
    DEFAULT_HISTORICAL_CSV,
    EXAM_METADATA,
    SUBJECT_MARKS_BY_SYLLABUS,
    TOPIC_REGISTRY,
    TopicMeta,
    ensure_historical_dataset,
    generate_historical_exam_dataset,
    get_topics_dict,
    is_topic_active_in_syllabus,
    load_historical_exam_counts,
)
from priority.model import (
    AllTimeFrequencyBaseline,
    DirichletMultinomialPriorityModel,
    LastExamBaseline,
    PriorityTier,
    TopicPriorityPrediction,
    UniformBaseline,
)
from priority.backtest import (
    DEFAULT_REPORT_PATH,
    EvalInstanceResult,
    WalkForwardBacktester,
    compute_metrics_for_distribution,
)

__all__ = [
    "DEFAULT_HISTORICAL_CSV",
    "EXAM_METADATA",
    "SUBJECT_MARKS_BY_SYLLABUS",
    "TOPIC_REGISTRY",
    "TopicMeta",
    "ensure_historical_dataset",
    "generate_historical_exam_dataset",
    "get_topics_dict",
    "is_topic_active_in_syllabus",
    "load_historical_exam_counts",
    "DirichletMultinomialPriorityModel",
    "TopicPriorityPrediction",
    "PriorityTier",
    "UniformBaseline",
    "AllTimeFrequencyBaseline",
    "LastExamBaseline",
    "DEFAULT_REPORT_PATH",
    "EvalInstanceResult",
    "WalkForwardBacktester",
    "compute_metrics_for_distribution",
]
