"""Data models and schemas for the /ingest pipeline."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class LineOCRResult(BaseModel):
    """OCR result for a single line of text."""
    line_num: int
    text: str
    confidence: float


class PageOCRResult(BaseModel):
    """OCR result for an entire page, with per-line and mean confidences."""
    page_num: int
    image_path: str
    tesseract_text: str
    mean_confidence: float
    lines: list[LineOCRResult] = Field(default_factory=list)
    vision_text: Optional[str] = None
    used_vision: bool = False
    final_text: str = ""


class RawParsedQuestion(BaseModel):
    """Individual parsed question extracted from page text."""
    q_no: int
    stem: str
    options: list[str]
    raw_text: Optional[str] = None


class ExtractedQuestionsPayload(BaseModel):
    """Schema expected from LLM structure extraction prompt B2."""
    questions: list[RawParsedQuestion] = Field(default_factory=list)


class IngestQuestionRecord(BaseModel):
    """Full question record throughout the ingestion and review lifecycle."""
    id: str
    bcs_number: int
    page_num: int
    q_no: int
    stem: str
    options: list[str]
    correct_index: Optional[int] = None
    explanation: Optional[str] = None
    topic_id: Optional[str] = None
    difficulty: Optional[float] = None
    flags: list[str] = Field(default_factory=list)
    status: str = "draft"  # draft, needs_review, verified, rejected
    approved: bool = False
    embedding: Optional[list[float]] = None


class ExamIngestReport(BaseModel):
    """Per-exam summary report of the ingestion run."""
    bcs_number: int
    total_pages: int
    questions_parsed: int
    questions_flagged: int
    questions_approved: int
    expected_questions: int
    flags_breakdown: dict[str, int] = Field(default_factory=dict)
    anomalies: list[str] = Field(default_factory=list)
