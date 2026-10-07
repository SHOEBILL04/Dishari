"""Tests for /taxonomy syllabus loader, embedder, kNN+LLM tagging, and evaluation."""

import json
from pathlib import Path
import tempfile
import pytest

from llm.client import LLMClient
from llm.providers.adapters import FakeProvider
from taxonomy.embedder import QuestionEmbedder
from taxonomy.gold_set import ensure_gold_dataset, load_and_split_gold_set
from taxonomy.loader import (
    format_candidate_topics_for_llm,
    get_all_topics_dict,
    load_taxonomy,
)
from taxonomy.tagger import TaxonomyTagger


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def fake_llm_client():
    fake_provider = FakeProvider(
        name="fake_taxonomy_llm",
        model="mock-disambiguate",
        responses=[
            {"topic_id": "top_bn_lit_ancient", "confidence": 0.95, "reasoning": "Direct mention of Charyapada."}
        ]
    )
    client = LLMClient(
        config={"active_chain": ["fake_taxonomy_llm"], "providers": {"fake_taxonomy_llm": {}}},
        providers={"fake_taxonomy_llm": fake_provider},
        active_chain=["fake_taxonomy_llm"],
    )
    return client, fake_provider


def test_load_taxonomy():
    """Verify loading taxonomy/bcs_topics.yaml correctly parses subjects and topics."""
    tax = load_taxonomy("bcs-35th-current")
    assert tax.version_id == "bcs-35th-current"
    assert tax.total_marks == 200.0
    assert len(tax.subjects) == 10

    subject_slugs = {s.slug for s in tax.subjects}
    assert "bangla" in subject_slugs
    assert "english" in subject_slugs
    assert "bangladesh_affairs" in subject_slugs
    assert "math" in subject_slugs

    # Verify topic dictionary
    all_topics = get_all_topics_dict("bcs-35th-current")
    assert len(all_topics) >= 25
    assert "top_bn_lit_ancient" in all_topics

    ancient_topic = all_topics["top_bn_lit_ancient"]
    assert ancient_topic.subject_slug == "bangla"
    assert "চর্যাপদ" in ancient_topic.keywords


def test_embedder_e5_prefixes():
    """Verify that e5 models correctly prepend 'query: ' and 'passage: '."""
    e5_embedder = QuestionEmbedder(model_name="intfloat/multilingual-e5-small")
    assert e5_embedder.is_e5 is True

    q_text = e5_embedder._prepare_text("চর্যাপদ কোন যুগে রচিত?", is_query=True)
    assert q_text.startswith("query: ")

    p_text = e5_embedder._prepare_text("চর্যাপদ বাংলা সাহিত্যের প্রাচীনতম নিদর্শন।", is_query=False)
    assert p_text.startswith("passage: ")

    # Non-e5 model should not add prefixes
    other_embedder = QuestionEmbedder(model_name="sentence-transformers/all-MiniLM-L6-v2")
    assert other_embedder.is_e5 is False
    assert not other_embedder._prepare_text("Test", is_query=True).startswith("query: ")


def test_format_candidate_topics_for_llm():
    """Verify formatting top-5 candidates into readable prompt text."""
    formatted = format_candidate_topics_for_llm(["top_bn_lit_ancient", "top_bn_gram_sandhi"])
    assert "top_bn_lit_ancient" in formatted
    assert "top_bn_gram_sandhi" in formatted
    assert "চর্যাপদ" in formatted


def test_gold_dataset_generation_and_split(temp_dir):
    """Test generating 300 gold records and stratified train/eval splitting."""
    gold_path = temp_dir / "gold.csv"
    ensure_gold_dataset(gold_path)
    assert gold_path.is_file()

    train_df, eval_df = load_and_split_gold_set(gold_path, test_size=0.25, random_state=42)
    assert len(train_df) + len(eval_df) == 300
    assert len(eval_df) == 75
    assert len(train_df) == 225

    # Check topic coverage in both splits
    train_topics = set(train_df["topic_id"])
    eval_topics = set(eval_df["topic_id"])
    assert len(train_topics) == len(eval_topics)


def test_knn_tagger_training_and_prediction(temp_dir):
    """Train kNN tagger on gold set and test prediction on unambiguous question."""
    gold_path = temp_dir / "gold.csv"
    train_df, eval_df = load_and_split_gold_set(gold_path, test_size=0.25)

    tagger = TaxonomyTagger(k_neighbors=5)
    tagger.fit(train_df)

    res = tagger.predict_one(
        stem="চর্যাপদের মূল পুঁথি কে আবিষ্কার করেন?",
        options=["হরপ্রসাদ শাস্ত্রী", "লুইপা", "কাহ্নপা", "দীনেশচন্দ্র সেন"],
        question_id="test_q1"
    )

    assert res.predicted_topic_id == "top_bn_lit_ancient"
    assert res.confidence >= 0.80
    assert res.needs_review is False
    assert len(res.candidate_topics) >= 1


def test_ambiguity_detection_and_llm_disambiguation(temp_dir, fake_llm_client):
    """Test that ambiguous close scores trigger LLM disambiguation prompt B4."""
    client, fake_provider = fake_llm_client
    fake_provider.set_responses([
        {"topic_id": "top_bn_lit_ancient", "confidence": 0.95, "reasoning": "Clear Charyapada poem"}
    ])

    gold_path = temp_dir / "gold.csv"
    train_df, _ = load_and_split_gold_set(gold_path, test_size=0.25)

    tagger = TaxonomyTagger(
        llm_client=client,
        k_neighbors=5,
        ambiguity_margin=0.99,  # High margin forces ambiguity branch
    )
    tagger.fit(train_df)

    res = tagger.predict_one(
        stem="চর্যাপদ ও মধ্যযুগের সাহিত্যিক ধারা",
        options=["ক", "খ", "গ", "ঘ"],
        question_id="ambig_q"
    )

    assert res.is_ambiguous is True
    assert res.used_llm is True
    assert res.predicted_topic_id == "top_bn_lit_ancient"
    assert res.reasoning == "Clear Charyapada poem"


def test_evaluation_on_gold_eval_set_meets_target(temp_dir):
    """Evaluate classifier on gold eval set and verify target >= 90% accuracy."""
    gold_path = temp_dir / "gold.csv"
    train_df, eval_df = load_and_split_gold_set(gold_path, test_size=0.25, random_state=42)

    tagger = TaxonomyTagger(k_neighbors=5)
    tagger.fit(train_df)

    report = tagger.evaluate(eval_df)

    # Check required metrics
    assert "overall_accuracy" in report
    assert "top_10_confused_pairs" in report
    assert "subject_breakdown" in report

    # Verify target >= 90% accuracy on gold eval set
    assert report["overall_accuracy"] >= 0.90, (
        f"Evaluation accuracy was {report['overall_accuracy']*100:.2f}%, which is below the 90% target!"
    )
    assert report["target_reached"] is True
