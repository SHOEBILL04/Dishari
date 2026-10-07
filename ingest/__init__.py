"""Ingest module for past BCS examination papers."""

from ingest.models import (
    ExamIngestReport,
    IngestQuestionRecord,
    LineOCRResult,
    PageOCRResult,
    RawParsedQuestion,
)
from ingest.preprocessor import (
    calculate_skew_angle,
    denoise_image,
    deskew_image,
    pdf_to_images,
    preprocess_page_image,
)
from ingest.ocr import extract_tesseract_ocr, process_page_ocr
from ingest.parser import (
    clean_bangla_text,
    extract_questions_from_page,
    get_expected_question_count,
    parse_questions_with_regex,
    validate_and_flag_exam_questions,
)
from ingest.answer_keys import load_answer_key_csv, merge_answer_keys
from ingest.dedupe import cosine_similarity, deduplicate_questions, generate_embedding
from ingest.pipeline import IngestPipeline, extract_bcs_number

__all__ = [
    "ExamIngestReport",
    "IngestQuestionRecord",
    "LineOCRResult",
    "PageOCRResult",
    "RawParsedQuestion",
    "calculate_skew_angle",
    "denoise_image",
    "deskew_image",
    "pdf_to_images",
    "preprocess_page_image",
    "extract_tesseract_ocr",
    "process_page_ocr",
    "clean_bangla_text",
    "extract_questions_from_page",
    "get_expected_question_count",
    "parse_questions_with_regex",
    "validate_and_flag_exam_questions",
    "load_answer_key_csv",
    "merge_answer_keys",
    "cosine_similarity",
    "deduplicate_questions",
    "generate_embedding",
    "IngestPipeline",
    "extract_bcs_number",
]
