"""Unit tests for /priority topic estimation and walk-forward backtesting."""

import numpy as np
import pytest

from priority.dataset import (
    generate_historical_exam_dataset,
    load_historical_exam_counts,
    SUBJECT_MARKS_BY_SYLLABUS,
    TOPIC_REGISTRY,
)
from priority.model import (
    AllTimeFrequencyBaseline,
    DirichletMultinomialPriorityModel,
    LastExamBaseline,
    PriorityTier,
    UniformBaseline,
)
from priority.backtest import (
    WalkForwardBacktester,
    compute_metrics_for_distribution,
)


@pytest.fixture
def historical_df():
    """Load or generate historical exam counts."""
    return load_historical_exam_counts()


def test_historical_dataset_question_counts(historical_df):
    """Verify that historical exam counts strictly match official syllabus mark quotas."""
    # Pre-35th exams (30-34) must have exactly 100 marks
    for e in range(30, 35):
        exam_total = historical_df[historical_df["bcs_number"] == e]["question_count"].sum()
        assert exam_total == 100, f"Exam {e} expected 100 questions, got {exam_total}"

    # 35th+ exams (35-45) must have exactly 200 marks
    for e in range(35, 46):
        exam_total = historical_df[historical_df["bcs_number"] == e]["question_count"].sum()
        assert exam_total == 200, f"Exam {e} expected 200 questions, got {exam_total}"

    # Check per-subject marks in 35th+
    exam_45 = historical_df[historical_df["bcs_number"] == 45]
    expected_35th_marks = SUBJECT_MARKS_BY_SYLLABUS["bcs-35th-current"]
    for sub, exp_marks in expected_35th_marks.items():
        sub_total = exam_45[exam_45["subject_slug"] == sub]["question_count"].sum()
        assert sub_total == exp_marks, f"Exam 45 subject {sub} expected {exp_marks}, got {sub_total}"


def test_model_share_sum_and_marks_conservation(historical_df):
    """Verify topic shares sum to 1.0 and expected questions sum to subject marks."""
    model = DirichletMultinomialPriorityModel(half_life=3.0, shrinkage=5.0)
    all_preds = model.predict_all_subjects(historical_df, current_exam_k=45)

    expected_marks = SUBJECT_MARKS_BY_SYLLABUS["bcs-35th-current"]
    for sub, preds in all_preds.items():
        assert len(preds) > 0, f"Subject {sub} has no topic predictions"
        share_sum = sum(p.posterior_mean_share for p in preds)
        exp_sum = sum(p.expected_questions for p in preds)

        assert abs(share_sum - 1.0) < 1e-3, f"Subject {sub} shares sum to {share_sum}, not 1.0"
        assert abs(exp_sum - expected_marks[sub]) < 1e-2, (
            f"Subject {sub} expected questions sum to {exp_sum}, not {expected_marks[sub]}"
        )


def test_credible_intervals_ordering(historical_df):
    """Verify that 80% credible intervals are valid: lower <= mean <= upper."""
    model = DirichletMultinomialPriorityModel(half_life=3.0, shrinkage=5.0)
    all_preds = model.predict_all_subjects(historical_df, current_exam_k=45)

    for sub, preds in all_preds.items():
        for p in preds:
            # Topic share CI
            assert 0.0 <= p.ci_80_lower <= p.posterior_mean_share <= p.ci_80_upper <= 1.0, (
                f"Invalid share CI for {p.topic_id}: [{p.ci_80_lower}, {p.posterior_mean_share}, {p.ci_80_upper}]"
            )
            # Question count CI
            assert 0.0 <= p.ci_80_questions_lower <= p.expected_questions <= p.ci_80_questions_upper, (
                f"Invalid question CI for {p.topic_id}: [{p.ci_80_questions_lower}, {p.expected_questions}, {p.ci_80_questions_upper}]"
            )


def test_syllabus_transition_newly_introduced_topics(historical_df):
    """Verify that topics introduced in 35th BCS are NOT penalized to 0 when predicting exam 35."""
    model = DirichletMultinomialPriorityModel(half_life=3.0, shrinkage=5.0)
    # Computer & IT was introduced at 35th BCS (not tested in exams 30..34)
    cs_preds = model.predict_subject(historical_df, current_exam_k=35, subject_slug="computer_it")

    assert len(cs_preds) == 3
    for p in cs_preds:
        # Should receive fair equal baseline share 1/3 (0.333), not 0.0
        assert abs(p.posterior_mean_share - (1.0 / 3.0)) < 1e-2
        assert abs(p.expected_questions - 5.0) < 0.1
        # Uncertainty interval should be non-zero
        assert p.ci_80_questions_lower < p.expected_questions < p.ci_80_questions_upper


def test_news_signal_adjustment(historical_df):
    """Verify news signal boosts targeted topic when enabled and ignores when disabled."""
    model = DirichletMultinomialPriorityModel(half_life=3.0, shrinkage=5.0, news_weight=2.0)

    # Base without news
    p_off = model.predict_subject(historical_df, 45, "international_affairs", news_enabled=False)
    base_geopolitics = next(p for p in p_off if p.topic_id == "top_int_geopolitics_security")

    # With news signal boosting geopolitics
    p_on = model.predict_subject(
        historical_df,
        45,
        "international_affairs",
        news_signal={"top_int_geopolitics_security": 5.0},
        news_enabled=True,
    )
    boosted_geopolitics = next(p for p in p_on if p.topic_id == "top_int_geopolitics_security")

    assert boosted_geopolitics.expected_questions > base_geopolitics.expected_questions
    assert boosted_geopolitics.posterior_mean_share > base_geopolitics.posterior_mean_share

    # News signal should not affect math or science
    math_off = model.predict_subject(historical_df, 45, "math", news_enabled=False)
    math_on = model.predict_subject(
        historical_df,
        45,
        "math",
        news_signal={"top_math_algebra": 5.0},
        news_enabled=True,
    )
    for m1, m2 in zip(math_off, math_on):
        assert m1.posterior_mean_share == m2.posterior_mean_share


def test_baselines_validity(historical_df):
    """Verify that all baseline methods output well-formed probability distributions."""
    uniform = UniformBaseline()
    alltime = AllTimeFrequencyBaseline()
    lastexam = LastExamBaseline()

    for sub in ["bangla", "english", "bangladesh_affairs", "computer_it"]:
        u_p = uniform.predict_shares(sub, 45, historical_df)
        at_p = alltime.predict_shares(sub, 45, historical_df)
        le_p = lastexam.predict_shares(sub, 45, historical_df)

        assert abs(sum(u_p.values()) - 1.0) < 1e-4
        assert abs(sum(at_p.values()) - 1.0) < 1e-4
        assert abs(sum(le_p.values()) - 1.0) < 1e-4


def test_walk_forward_backtest_mini_run(historical_df, tmp_path):
    """Run a fast walk-forward test over exams 43..45 and verify report generation."""
    report_file = tmp_path / "test_backtest_report.md"
    tester = WalkForwardBacktester(
        historical_df=historical_df,
        eval_exams=[43, 44, 45],
        bootstrap_iterations=50,
    )
    results = tester.run_backtest()

    assert len(results) == 30  # 3 exams * 10 subjects
    report_text = tester.generate_report(results, output_path=report_file)

    assert report_file.is_file()
    assert "Executive Summary & Plain Verdict" in report_text
    assert "Dirichlet-Multinomial Model" in report_text
    assert "Priority Tiers" in report_text
