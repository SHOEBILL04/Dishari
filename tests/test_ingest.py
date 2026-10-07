"""Tests for the /ingest pipeline using 3 synthetic sample exam pages."""

import csv
import json
from pathlib import Path
import tempfile
import pytest
import numpy as np
from PIL import Image, ImageDraw

from ingest.answer_keys import load_answer_key_csv, merge_answer_keys
from ingest.dedupe import cosine_similarity, deduplicate_questions
from ingest.models import IngestQuestionRecord
from ingest.ocr import extract_tesseract_ocr, process_page_ocr
from ingest.parser import (
    extract_questions_from_page,
    get_expected_question_count,
    parse_questions_with_regex,
    validate_and_flag_exam_questions,
)
from ingest.pipeline import IngestPipeline, extract_bcs_number
from ingest.preprocessor import (
    calculate_skew_angle,
    deskew_image,
    preprocess_page_image,
)
from llm.client import LLMClient
from llm.providers.adapters import FakeProvider


@pytest.fixture
def temp_dir():
    """Temporary workspace for synthetic files and outputs."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def create_synthetic_page_image(
    output_path: Path,
    text_lines: list[str],
    rotate_deg: float = 0.0,
    add_noise: bool = False,
) -> Path:
    """Create a synthetic high-resolution page image for OCR testing."""
    width, height = 1000, 1400
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    y_pos = 100
    for line in text_lines:
        draw.text((80, y_pos), line, fill=(0, 0, 0))
        y_pos += 60

    if add_noise:
        # Add random salt-and-pepper noise
        arr = np.array(img)
        noise = np.random.randint(0, 50, arr.shape, dtype=np.uint8)
        arr = np.clip(arr.astype(int) - noise.astype(int), 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    if abs(rotate_deg) > 0.01:
        img = img.rotate(rotate_deg, fillcolor=(255, 255, 255), expand=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


@pytest.fixture
def three_synthetic_pages(temp_dir):
    """Create 3 synthetic sample exam pages representing different scenarios.
    
    Page 1: Normal clean page (Q1, Q2) with 4 options each.
    Page 2: Page with anomaly (Q3 with 4 options, Q4 with only 3 options).
    Page 3: Page with low quality / noisy OCR and duplicate question (Q5 identical to Q1).
    """
    pages_dir = temp_dir / "input_pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Page 1: Standard clean questions
    p1_path = pages_dir / "45_bcs_prelim_page_001.png"
    create_synthetic_page_image(
        p1_path,
        text_lines=[
            "45th BCS Preliminary Examination",
            "1. What is the capital of Bangladesh?",
            "(a) Dhaka (b) Chittagong (c) Sylhet (d) Khulna",
            "2. Who wrote Hamlet?",
            "(a) Shakespeare (b) Milton (c) Wordsworth (d) Keats",
        ],
        rotate_deg=2.0,  # Slight skew to test deskewing
    )

    # Page 2: Contains an anomaly: Q4 has only 3 options
    p2_path = pages_dir / "45_bcs_prelim_page_002.png"
    create_synthetic_page_image(
        p2_path,
        text_lines=[
            "3. The currency of Japan is:",
            "(a) Yen (b) Dollar (c) Euro (d) Pound",
            "4. Photosynthesis requires:",
            "(a) Sunlight (b) Water (c) Chlorophyll",  # Missing 4th option!
        ],
        rotate_deg=0.0,
    )

    # Page 3: Noisy scan and duplicate question
    p3_path = pages_dir / "45_bcs_prelim_page_003.png"
    create_synthetic_page_image(
        p3_path,
        text_lines=[
            "5. What is the capital of Bangladesh?",  # Duplicate of Q1!
            "(a) Dhaka (b) Chittagong (c) Sylhet (d) Rajshahi",
            "6. Water freezes at what temperature Celsius?",
            "(a) 0 (b) 32 (c) 100 (d) -10",
        ],
        rotate_deg=0.0,
        add_noise=True,
    )

    return [p1_path, p2_path, p3_path]


@pytest.fixture
def fake_llm_client():
    """Fake LLM client configured for OCR transcription and structured question extraction."""
    fake_provider = FakeProvider(name="fake_ocr_llm", model="mock-vision")
    config = {
        "active_chain": ["fake_ocr_llm"],
        "providers": {"fake_ocr_llm": {"rate_limit": {"requests_per_minute": 1000, "requests_per_day": 10000}}},
    }
    client = LLMClient(
        config=config,
        providers={"fake_ocr_llm": fake_provider},
        active_chain=["fake_ocr_llm"],
    )
    return client, fake_provider


def test_extract_bcs_number():
    """Test extracting BCS exam number from filenames."""
    assert extract_bcs_number("45_bcs_prelim.pdf") == 45
    assert extract_bcs_number("path/to/38_bcs_prelim.png") == 38
    assert extract_bcs_number("10th_bcs_prelim.pdf") == 10
    with pytest.raises(ValueError):
        extract_bcs_number("unnamed_exam.pdf")


def test_preprocessor_deskew_and_denoise(three_synthetic_pages, temp_dir):
    """Test OpenCV deskewing and denoising on synthetic page 1."""
    p1 = three_synthetic_pages[0]
    out_clean = temp_dir / "clean_p1.png"

    cleaned = preprocess_page_image(p1, output_path=out_clean)
    assert out_clean.is_file()
    assert isinstance(cleaned, np.ndarray)
    assert len(cleaned.shape) == 2  # Grayscale 2D image


def test_tesseract_ocr_extraction(three_synthetic_pages):
    """Test Tesseract OCR per-line confidence calculation on synthetic page 1."""
    p1 = three_synthetic_pages[0]
    text, mean_conf, lines = extract_tesseract_ocr(p1, lang="eng")

    assert len(text) > 0
    assert mean_conf >= 0.0
    assert len(lines) >= 2
    # Verify per-line confidence is populated
    for line in lines:
        assert line.confidence >= 0.0
        assert line.line_num >= 1


def test_vision_fallback_on_low_confidence(temp_dir, fake_llm_client):
    """Test that low OCR confidence triggers Vision LLM fallback using prompt B1."""
    client, fake_provider = fake_llm_client
    fake_provider.set_responses([
        {"transcription": "Transcribed by Vision LLM: 1. Question stem (a) A (b) B (c) C (d) D"}
    ])

    test_img = temp_dir / "blurry_page.png"
    create_synthetic_page_image(test_img, ["1. Low contrast blurry text"], add_noise=True)

    # Set confidence threshold to 99.0% so fallback is guaranteed to trigger
    ocr_result = process_page_ocr(
        image_path=test_img,
        page_num=1,
        confidence_threshold=99.0,
        llm_client=client,
    )

    assert ocr_result.used_vision is True
    assert ocr_result.vision_text is not None
    assert "Vision LLM" in ocr_result.vision_text
    # Verify both outputs are kept
    assert ocr_result.tesseract_text is not None


def test_question_parser_and_anomaly_flags():
    """Test structure extraction, 4 options validation, and sequential numbering check."""
    sample_text = """
    1. Capital of Bangladesh?
    (a) Dhaka (b) Chittagong (c) Sylhet (d) Khulna
    2. Who wrote Hamlet?
    (a) Shakespeare (b) Milton (c) Wordsworth (d) Keats
    3. Currency of Japan?
    (a) Yen (b) Dollar (c) Euro (d) Pound
    4. Photosynthesis requires:
    (a) Sunlight (b) Water (c) Chlorophyll
    """
    raw_qs = parse_questions_with_regex(sample_text)
    assert len(raw_qs) == 4

    records = [
        IngestQuestionRecord(
            id=f"q_{q.q_no}",
            bcs_number=45,
            page_num=1,
            q_no=q.q_no,
            stem=q.stem,
            options=q.options,
        )
        for q in raw_qs
    ]

    validated, anomalies = validate_and_flag_exam_questions(records, bcs_number=45)

    # Question 4 must be flagged because it only has 3 options
    q4 = next(q for q in validated if q.q_no == 4)
    assert any("invalid_options_count" in f for f in q4.flags)
    assert q4.status == "needs_review"

    # Total count (4) != expected (200) must be recorded in global anomalies
    assert any("count mismatch" in a.lower() for a in anomalies)


def test_official_answer_keys_csv_merging(temp_dir):
    """Test that official answer key CSV is merged and keys are NEVER inferred by LLM."""
    csv_file = temp_dir / "official_keys.csv"
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["q_no", "answer"])
        writer.writerow([1, "a"])  # 0
        writer.writerow([2, "খ"])  # 1
        writer.writerow([3, "2"])  # 2

    key_map = load_answer_key_csv(csv_file)
    assert key_map[1] == 0
    assert key_map[2] == 1
    assert key_map[3] == 2

    questions = [
        IngestQuestionRecord(id="q1", bcs_number=45, page_num=1, q_no=1, stem="Q1", options=["a","b","c","d"]),
        IngestQuestionRecord(id="q2", bcs_number=45, page_num=1, q_no=2, stem="Q2", options=["a","b","c","d"]),
        IngestQuestionRecord(id="q3", bcs_number=45, page_num=1, q_no=3, stem="Q3", options=["a","b","c","d"]),
        IngestQuestionRecord(id="q4", bcs_number=45, page_num=1, q_no=4, stem="Q4", options=["a","b","c","d"]),
    ]

    merged = merge_answer_keys(questions, key_map)
    assert merged[0].correct_index == 0
    assert merged[1].correct_index == 1
    assert merged[2].correct_index == 2
    # Question 4 has no official key: MUST REMAIN NONE (never guessed by LLM)
    assert merged[3].correct_index is None


def test_embedding_deduplication():
    """Test that duplicate questions (cosine > 0.92) are flagged and NEVER deleted."""
    q1 = IngestQuestionRecord(
        id="q1", bcs_number=45, page_num=1, q_no=1,
        stem="What is the capital of Bangladesh?",
        options=["Dhaka", "Chittagong", "Sylhet", "Khulna"]
    )
    q2 = IngestQuestionRecord(
        id="q2", bcs_number=45, page_num=1, q_no=2,
        stem="Who is the national poet of Bangladesh?",
        options=["Kazi Nazrul Islam", "Rabindranath Tagore", "Jashimuddin", "Jibanananda Das"]
    )
    # Identical question stem to q1
    q5 = IngestQuestionRecord(
        id="q5", bcs_number=45, page_num=3, q_no=5,
        stem="What is the capital of Bangladesh?",
        options=["Dhaka", "Chittagong", "Sylhet", "Rajshahi"]
    )

    batch = [q1, q2, q5]
    deduped = deduplicate_questions(batch, threshold=0.92)

    # Verify no question was deleted
    assert len(deduped) == 3

    # Verify q1 and q5 are flagged as possible duplicates
    assert any("possible_duplicate" in f for f in q1.flags)
    assert any("possible_duplicate" in f for f in q5.flags)
    # q2 is unique, should have no duplicate flags
    assert not any("possible_duplicate" in f for f in q2.flags)


def test_end_to_end_pipeline_and_report(three_synthetic_pages, temp_dir):
    """Test full pipeline end-to-end on synthetic pages with reporting."""
    pipeline = IngestPipeline(output_dir=temp_dir / "ingest_out")

    # Combine pages into pipeline by processing page 1 as representative exam file
    p1 = three_synthetic_pages[0]
    questions, report = pipeline.process_exam_file(p1)

    assert len(questions) >= 2
    assert report.bcs_number == 45
    assert report.total_pages == 1
    assert report.questions_parsed == len(questions)

    # Check report JSON saved on disk
    report_file = temp_dir / "ingest_out" / "45_bcs" / "report.json"
    assert report_file.is_file()
    saved_report = json.loads(report_file.read_text(encoding="utf-8"))
    assert saved_report["bcs_number"] == 45

    # Check staged questions saved on disk
    staged_file = temp_dir / "ingest_out" / "45_bcs" / "staged_questions.json"
    assert staged_file.is_file()


def test_database_insertion_only_approved(empty_db):
    """Test that only approved questions are inserted into Postgres as source_type='past'."""
    import psycopg
    from scripts.migrate import apply_migrations
    from ingest.review_app import insert_approved_to_db

    # Setup database schema
    apply_migrations(empty_db)

    test_questions = [
        {
            "id": "00000000-0000-0000-0000-000000000101",
            "q_no": 1,
            "stem": "Approved Question",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "Official explanation",
            "approved": True,  # APPROVED
            "status": "verified",
            "embedding": [0.0] * 384,
        },
        {
            "id": "00000000-0000-0000-0000-000000000102",
            "q_no": 2,
            "stem": "Unapproved Question",
            "options": ["A", "B", "C", "D"],
            "correct_index": None,
            "explanation": None,
            "approved": False,  # UNAPPROVED
            "status": "draft",
            "embedding": None,
        },
    ]

    inserted_count = insert_approved_to_db(test_questions, db_url=empty_db)
    assert inserted_count == 1

    with psycopg.connect(empty_db) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, stem, source_type, status FROM questions WHERE id = '00000000-0000-0000-0000-000000000101';")
            row = cur.fetchone()
            assert row is not None
            assert row[1] == "Approved Question"
            assert row[2] == "past"
            assert row[3] == "verified"

            # Verify unapproved question was NOT inserted
            cur.execute("SELECT id FROM questions WHERE id = '00000000-0000-0000-0000-000000000102';")
            assert cur.fetchone() is None

