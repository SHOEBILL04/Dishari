"""End-to-end ingestion pipeline coordinating PDF/image conversion, OCR, extraction, and validation."""

import json
from pathlib import Path
import re
from typing import Optional, Union
import uuid

from ingest.answer_keys import load_answer_key_csv, merge_answer_keys
from ingest.dedupe import deduplicate_questions
from ingest.models import (
    ExamIngestReport,
    IngestQuestionRecord,
    PageOCRResult,
)
from ingest.ocr import process_page_ocr
from ingest.parser import (
    extract_questions_from_page,
    get_expected_question_count,
    validate_and_flag_exam_questions,
)
from ingest.preprocessor import pdf_to_images, preprocess_page_image
from llm.client import LLMClient

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "ingest"


def extract_bcs_number(file_path: Union[str, Path]) -> int:
    """Extract BCS exam number from file name (e.g. '45_bcs_prelim.pdf' -> 45)."""
    name = Path(file_path).stem
    match = re.search(r"(\d+)", name)
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not extract BCS number from filename: {name}")


class IngestPipeline:
    """Orchestrates PDF/image conversion, OCR, LLM extraction, answer keys, and deduplication."""

    def __init__(
        self,
        output_dir: Path = DEFAULT_DATA_DIR,
        llm_client: Optional[LLMClient] = None,
        confidence_threshold: float = 60.0,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold

    def process_exam_file(
        self,
        file_path: Union[str, Path],
        answer_key_csv: Optional[Union[str, Path]] = None,
        existing_questions: Optional[list[IngestQuestionRecord]] = None,
    ) -> tuple[list[IngestQuestionRecord], ExamIngestReport]:
        """Process a single BCS exam PDF or image file.
        
        Args:
            file_path: Path to exam PDF or image file (e.g. '45_bcs_prelim.pdf').
            answer_key_csv: Optional CSV containing official answer keys.
            existing_questions: List of already approved questions for cross-exam deduplication.
            
        Returns:
            Tuple of (all_question_records, exam_report).
        """
        fpath = Path(file_path)
        bcs_num = extract_bcs_number(fpath)
        exam_dir = self.output_dir / f"{bcs_num}_bcs"
        pages_dir = exam_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Convert pages to 300 DPI images and preprocess
        if fpath.suffix.lower() == ".pdf":
            raw_page_paths = pdf_to_images(fpath, pages_dir, dpi=300)
        else:
            # Single image file (PNG, JPG)
            raw_page_paths = [fpath]

        preprocessed_paths = []
        for p_idx, raw_p in enumerate(raw_page_paths, start=1):
            clean_out = pages_dir / f"clean_page_{p_idx:03d}.png"
            preprocess_page_image(raw_p, output_path=clean_out)
            preprocessed_paths.append(clean_out)

        # Step 2 & 3: Run OCR (Tesseract ben+eng) and Vision LLM fallback
        ocr_results: list[PageOCRResult] = []
        all_raw_questions = []

        for p_idx, page_img in enumerate(preprocessed_paths, start=1):
            ocr_res = process_page_ocr(
                image_path=page_img,
                page_num=p_idx,
                confidence_threshold=self.confidence_threshold,
                llm_client=self.llm_client,
                notes=f"Exam: {bcs_num}th BCS, Page {p_idx}",
            )
            ocr_results.append(ocr_res)

            # Step 4: Parse into question records using prompt B2
            page_questions = extract_questions_from_page(
                page_text=ocr_res.final_text,
                page_num=p_idx,
                bcs_number=bcs_num,
                llm_client=self.llm_client,
            )

            for raw_q in page_questions:
                flags = []
                if ocr_res.used_vision:
                    flags.append("transcribed_with_vision_llm")
                elif ocr_res.mean_confidence < self.confidence_threshold:
                    flags.append(f"low_ocr_confidence: {ocr_res.mean_confidence}%")

                q_record = IngestQuestionRecord(
                    id=str(uuid.uuid4()),
                    bcs_number=bcs_num,
                    page_num=p_idx,
                    q_no=raw_q.q_no,
                    stem=raw_q.stem,
                    options=raw_q.options,
                    flags=flags,
                    status="draft",
                    approved=False,
                )
                all_raw_questions.append(q_record)

        # Sort questions by q_no
        all_raw_questions.sort(key=lambda x: (x.q_no, x.page_num))

        # Step 5: Answer keys from CSV (never infer with LLM)
        if answer_key_csv:
            ans_map = load_answer_key_csv(answer_key_csv)
            all_raw_questions = merge_answer_keys(all_raw_questions, ans_map)

        # Step 6: Deduplication via embeddings (cosine > 0.92 flagged, never auto-deleted)
        all_raw_questions = deduplicate_questions(
            all_raw_questions,
            existing_questions=existing_questions,
            threshold=0.92,
        )

        # Step 7: Validate 4 options, contiguous numbers, and total count
        all_raw_questions, anomalies = validate_and_flag_exam_questions(
            all_raw_questions,
            bcs_number=bcs_num,
        )

        # Step 8: Build Exam Report
        flags_breakdown: dict[str, int] = {}
        flagged_count = 0
        approved_count = 0

        for q in all_raw_questions:
            if q.approved:
                approved_count += 1
            if q.flags:
                flagged_count += 1
                for f in q.flags:
                    prefix = f.split(":")[0]
                    flags_breakdown[prefix] = flags_breakdown.get(prefix, 0) + 1

        expected_count = get_expected_question_count(bcs_num)
        report = ExamIngestReport(
            bcs_number=bcs_num,
            total_pages=len(preprocessed_paths),
            questions_parsed=len(all_raw_questions),
            questions_flagged=flagged_count,
            questions_approved=approved_count,
            expected_questions=expected_count,
            flags_breakdown=flags_breakdown,
            anomalies=anomalies,
        )

        # Save staged questions and report
        staged_file = exam_dir / "staged_questions.json"
        staged_file.write_text(
            json.dumps([q.model_dump() for q in all_raw_questions], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        report_file = exam_dir / "report.json"
        report_file.write_text(
            json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return all_raw_questions, report
