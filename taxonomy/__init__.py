"""Taxonomy module for BCS syllabus hierarchies, embedders, and topic classification."""

from taxonomy.embedder import QuestionEmbedder, get_embedder
from taxonomy.gold_set import (
    DEFAULT_GOLD_CSV_PATH,
    ensure_gold_dataset,
    generate_300_gold_records,
    load_and_split_gold_set,
)
from taxonomy.loader import (
    DEFAULT_TAXONOMY_PATH,
    SubjectTaxonomy,
    SyllabusTaxonomy,
    TopicNode,
    format_candidate_topics_for_llm,
    get_all_topics_dict,
    load_taxonomy,
)
from taxonomy.tagger import DisambiguationOutput, TaggingResult, TaxonomyTagger

__all__ = [
    "QuestionEmbedder",
    "get_embedder",
    "DEFAULT_TAXONOMY_PATH",
    "DEFAULT_GOLD_CSV_PATH",
    "TopicNode",
    "SubjectTaxonomy",
    "SyllabusTaxonomy",
    "load_taxonomy",
    "get_all_topics_dict",
    "format_candidate_topics_for_llm",
    "ensure_gold_dataset",
    "generate_300_gold_records",
    "load_and_split_gold_set",
    "DisambiguationOutput",
    "TaggingResult",
    "TaxonomyTagger",
]
