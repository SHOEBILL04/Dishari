"""Structure extraction and question validation module for /ingest."""

import re
from typing import Any, Optional
import unicodedata
import yaml
from pathlib import Path

from ingest.models import (
    ExtractedQuestionsPayload,
    IngestQuestionRecord,
    RawParsedQuestion,
)
from llm.client import complete, LLMClient

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "exam_rules.yaml"


def get_expected_question_count(bcs_number: int, config_path: Path = DEFAULT_RULES_PATH) -> int:
    """Read expected question count from config/exam_rules.yaml based on BCS number."""
    if config_path.is_file():
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        # 35th BCS onwards is 200 marks/questions, earlier exams were 100
        if bcs_number >= 35:
            return 200
        else:
            return 100
    return 200 if bcs_number >= 35 else 100


def clean_bangla_text(text: str) -> str:
    """Normalize text into standard Unicode NFC Bangla and strip whitespace."""
    return unicodedata.normalize("NFC", text).strip()


def parse_questions_with_regex(text: str) -> list[RawParsedQuestion]:
    """Fallback deterministic parser extracting MCQs with 4 options from raw text."""
    # Pattern to match: 1. Question text or ১. Question text
    q_pattern = re.compile(
        r"(?:^|\n)\s*(\d+|[০-৯]+)[\.\,\:\-\)]+\s*(.+?)(?=(?:\n\s*(?:\d+|[০-৯]+)[\.\,\:\-\)]+)|\Z)",
        re.DOTALL
    )

    bangla_digits = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    option_marker_pattern = re.compile(
        r"(?:(?<=\s)|(?<=^))(?:[\(\[\{][কখগঘa-dA-D1-4১-৪@][\)\]\}]|(?:[কখগঘa-dA-D1-4১-৪])[\.\)\:\-])\s*"
    )

    results: list[RawParsedQuestion] = []
    matches = q_pattern.findall(text)

    for num_str, body in matches:
        q_no_int = int(num_str.translate(bangla_digits))
        
        # Split options by standard Bangla markers (ক), (খ), (গ), (ঘ)
        opt_splits = option_marker_pattern.split(body)
        if len(opt_splits) >= 5:
            stem = clean_bangla_text(opt_splits[0])
            options = [clean_bangla_text(opt) for opt in opt_splits[1:5]]
        else:
            # Fallback: check lines
            lines = [l.strip() for l in body.splitlines() if l.strip()]
            if len(lines) >= 5:
                stem = clean_bangla_text(lines[0])
                options = [clean_bangla_text(opt) for opt in lines[1:5]]
            else:
                stem = clean_bangla_text(body)
                options = []

        results.append(
            RawParsedQuestion(
                q_no=q_no_int,
                stem=stem,
                options=options,
                raw_text=body.strip(),
            )
        )

    return results


def extract_questions_from_page(
    page_text: str,
    page_num: int,
    bcs_number: int,
    llm_client: Optional[LLMClient] = None,
) -> list[RawParsedQuestion]:
    """Extract question records from page text using Prompt B2 with regex fallback."""
    if not page_text.strip():
        return []

    # Attempt LLM structured extraction first
    try:
        res = complete(
            prompt_name="b2_extract_questions",
            variables={"page_text": page_text},
            schema=ExtractedQuestionsPayload,
            temperature=0.0,
            client=llm_client,
        )
        if res.questions:
            return res.questions
    except Exception:
        pass

    # Deterministic fallback
    return parse_questions_with_regex(page_text)


def validate_and_flag_exam_questions(
    questions: list[IngestQuestionRecord],
    bcs_number: int,
    config_path: Path = DEFAULT_RULES_PATH,
) -> tuple[list[IngestQuestionRecord], list[str]]:
    """Validate exam questions according to BCS rules and flag anomalies.
    
    Checks:
    1. Exactly 4 options per question.
    2. Contiguous question numbers (1, 2, 3... N).
    3. Total count matches expected exam question count.
    
    Returns:
        Tuple of (updated_questions, global_anomalies).
    """
    expected_count = get_expected_question_count(bcs_number, config_path)
    global_anomalies: list[str] = []

    # Check 1: Options count per question
    for q in questions:
        if len(q.options) != 4:
            q.flags.append(f"invalid_options_count: {len(q.options)} (expected 4)")
            q.status = "needs_review"

    # Check 2: Contiguous numbering & duplicates
    seen_qnos = set()
    duplicate_qnos = set()
    for q in questions:
        if q.q_no in seen_qnos:
            duplicate_qnos.add(q.q_no)
            q.flags.append(f"duplicate_q_no: {q.q_no}")
            q.status = "needs_review"
        seen_qnos.add(q.q_no)

    if duplicate_qnos:
        global_anomalies.append(f"Duplicate question numbers found: {sorted(duplicate_qnos)}")

    if seen_qnos:
        min_q = min(seen_qnos)
        max_q = max(seen_qnos)
        expected_seq = set(range(min_q, max_q + 1))
        missing_seq = expected_seq - seen_qnos
        if missing_seq:
            global_anomalies.append(
                f"Missing sequential question numbers: {sorted(missing_seq)}"
            )
            for q in questions:
                # Mark neighboring questions if gap
                if (q.q_no + 1) in missing_seq:
                    q.flags.append(f"gap_after_this: next is {q.q_no + 2} not {q.q_no + 1}")

    # Check 3: Total count matches expected exam question count
    total_parsed = len(questions)
    if total_parsed != expected_count:
        global_anomalies.append(
            f"Total question count mismatch: found {total_parsed}, expected {expected_count} for {bcs_number}th BCS"
        )

    return questions, global_anomalies
