"""OCR module for /ingest: Tesseract (ben+eng) with per-line confidence and Vision LLM fallback."""

from collections import defaultdict
from pathlib import Path
from typing import Optional, Union
import unicodedata
import cv2
import numpy as np
from PIL import Image

try:
    import pytesseract
    from pytesseract import Output
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

from ingest.models import LineOCRResult, PageOCRResult
from llm.client import complete, LLMClient

DEFAULT_TESSDATA_DIR = Path(__file__).resolve().parent.parent / "data" / "tessdata"


def extract_tesseract_ocr(
    image_input: Union[str, Path, np.ndarray, Image.Image],
    tessdata_dir: Optional[Path] = None,
    lang: str = "ben+eng",
) -> tuple[str, float, list[LineOCRResult]]:
    """Execute Tesseract OCR and extract text along with line-by-line and page confidence.
    
    Returns:
        Tuple of (raw_text: str, mean_confidence: float, lines: list[LineOCRResult]).
    """
    if not HAS_PYTESSERACT:
        raise ImportError("pytesseract is required. Install with: pip install pytesseract")

    # Load image if file path
    if isinstance(image_input, (str, Path)):
        img = Image.open(str(image_input))
    elif isinstance(image_input, np.ndarray):
        img = Image.fromarray(image_input)
    else:
        img = image_input

    t_dir = tessdata_dir or DEFAULT_TESSDATA_DIR
    config_args = f'--tessdata-dir "{t_dir}"' if t_dir.exists() else ""

    data = pytesseract.image_to_data(
        img,
        lang=lang,
        output_type=Output.DICT,
        config=config_args,
    )

    # Group words into physical lines using (block_num, par_num, line_num)
    lines_dict = defaultdict(list)
    n_boxes = len(data["text"])

    for i in range(n_boxes):
        word = data["text"][i].strip()
        conf = float(data["conf"][i])

        # Skip empty boxes or separator markers (-1 confidence)
        if not word or conf < 0:
            continue

        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines_dict[key].append((word, conf))

    parsed_lines: list[LineOCRResult] = []
    line_confidences: list[float] = []
    full_text_lines: list[str] = []

    for line_idx, (_, words) in enumerate(sorted(lines_dict.items()), start=1):
        line_text = " ".join(w[0] for w in words).strip()
        if not line_text:
            continue

        line_conf = sum(w[1] for w in words) / len(words)
        normalized_line_text = unicodedata.normalize("NFC", line_text)

        parsed_lines.append(
            LineOCRResult(
                line_num=line_idx,
                text=normalized_line_text,
                confidence=round(line_conf, 2),
            )
        )
        line_confidences.append(line_conf)
        full_text_lines.append(normalized_line_text)

    mean_conf = (
        round(sum(line_confidences) / len(line_confidences), 2)
        if line_confidences else 0.0
    )
    raw_text = "\n".join(full_text_lines)

    return raw_text, mean_conf, parsed_lines


def process_page_ocr(
    image_path: Union[str, Path],
    page_num: int,
    confidence_threshold: float = 60.0,
    llm_client: Optional[LLMClient] = None,
    tessdata_dir: Optional[Path] = None,
    notes: str = "",
) -> PageOCRResult:
    """Run Tesseract OCR on a page. If mean confidence is below threshold, fallback to Vision LLM.
    
    Both outputs are preserved in the result.
    """
    img_path = Path(image_path)
    tess_text, mean_conf, lines = extract_tesseract_ocr(
        img_path,
        tessdata_dir=tessdata_dir
    )

    used_vision = False
    vision_text = None

    if mean_conf < confidence_threshold:
        # Trigger Prompt B1 for vision-capable LLM transcription
        prompt_vars = {
            "notes": notes or f"Page {page_num} image at {img_path.name}. Low Tesseract confidence: {mean_conf}%"
        }
        try:
            from pydantic import BaseModel
            class VisionOutput(BaseModel):
                transcription: str

            res = complete(
                prompt_name="b1_vision_ocr",
                variables=prompt_vars,
                schema=VisionOutput,
                temperature=0.0,
                client=llm_client,
            )
            vision_text = unicodedata.normalize("NFC", res.transcription.strip())
            used_vision = True
        except Exception:
            # Fallback to raw tesseract if vision call unavailable
            vision_text = None
            used_vision = False

    final_text = (vision_text if used_vision and vision_text else tess_text)

    return PageOCRResult(
        page_num=page_num,
        image_path=str(img_path),
        tesseract_text=tess_text,
        mean_confidence=mean_conf,
        lines=lines,
        vision_text=vision_text,
        used_vision=used_vision,
        final_text=final_text,
    )
