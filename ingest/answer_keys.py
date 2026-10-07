"""Official answer key loader and merger for /ingest."""

import csv
from pathlib import Path
from typing import Optional, Union

from ingest.models import IngestQuestionRecord

BANGLA_OPTION_MAP = {
    "ক": 0, "খ": 1, "গ": 2, "ঘ": 3,
    "a": 0, "b": 1, "c": 2, "d": 3,
    "A": 0, "B": 1, "C": 2, "D": 3,
    "১": 0, "২": 1, "৩": 2, "৪": 3,
}


def parse_answer_token(val: str) -> Optional[int]:
    """Parse a single answer cell (letter or digit) to a 0-indexed integer (0, 1, 2, 3)."""
    val = val.strip()
    if not val:
        return None

    if val in BANGLA_OPTION_MAP:
        return BANGLA_OPTION_MAP[val]

    try:
        num = int(val)
        # If user provided 0-indexed values
        if 0 <= num <= 3:
            return num
        # If user provided 1-indexed values (1, 2, 3, 4)
        if 1 <= num <= 4:
            return num - 1
    except ValueError:
        pass

    return None


def load_answer_key_csv(csv_path: Optional[Union[str, Path]]) -> dict[int, int]:
    """Read an official answer key CSV.
    
    Expected CSV columns: q_no, answer (or question, key).
    Never infers answer keys via LLM; returns empty dict if CSV does not exist.
    """
    if not csv_path:
        return {}

    path = Path(csv_path)
    if not path.is_file():
        return {}

    key_map: dict[int, int] = {}
    with open(path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = None
        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue

            # Detect header
            first_cell = row[0].strip().lower()
            if first_cell in ("q_no", "question", "q", "sl", "no", "number") and header is None:
                header = row
                continue

            # Parse (q_no, answer)
            try:
                q_no = int(row[0].strip())
                ans_token = row[1].strip() if len(row) > 1 else ""
                idx = parse_answer_token(ans_token)
                if idx is not None:
                    key_map[q_no] = idx
            except (ValueError, IndexError):
                continue

    return key_map


def merge_answer_keys(
    questions: list[IngestQuestionRecord],
    answer_keys: dict[int, int],
) -> list[IngestQuestionRecord]:
    """Merge official answer keys into parsed questions without guessing missing keys."""
    for q in questions:
        if q.q_no in answer_keys:
            q.correct_index = answer_keys[q.q_no]
        else:
            q.correct_index = None
    return questions
