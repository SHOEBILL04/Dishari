"""Streamlit local review tool for verifying and approving ingested past BCS questions."""

import json
from pathlib import Path
import os
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "ingest"


def load_staged_data(exam_dir: Path):
    """Load staged questions and report from disk."""
    staged_path = exam_dir / "staged_questions.json"
    report_path = exam_dir / "report.json"

    questions = []
    report = {}

    if staged_path.is_file():
        questions = json.loads(staged_path.read_text(encoding="utf-8"))
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))

    return questions, report


def save_staged_data(exam_dir: Path, questions: list):
    """Save updated questions back to disk."""
    staged_path = exam_dir / "staged_questions.json"
    staged_path.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def insert_approved_to_db(questions: list, db_url: str = None):
    """Insert only approved questions into Postgres with source_type='past'."""
    import psycopg

    approved_qs = [q for q in questions if q.get("approved")]
    if not approved_qs:
        return 0

    url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dishari")
    count = 0

    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for q in approved_qs:
                cur.execute(
                    """
                    INSERT INTO questions (
                        id, source_type, q_no, stem, options, correct_index, 
                        explanation, status, embedding
                    ) VALUES (
                        %s, 'past', %s, %s, %s::jsonb, %s, %s, 'verified', %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        stem = EXCLUDED.stem,
                        options = EXCLUDED.options,
                        correct_index = EXCLUDED.correct_index,
                        explanation = EXCLUDED.explanation,
                        status = 'verified';
                    """,
                    (
                        q["id"],
                        q["q_no"],
                        q["stem"],
                        json.dumps(q["options"], ensure_ascii=False),
                        q.get("correct_index"),
                        q.get("explanation"),
                        q.get("embedding"),
                    )
                )
                count += 1
    return count


def main():
    st.set_page_config(page_title="Dishari - Ingestion Review Tool", layout="wide")
    st.title("Dishari: Past BCS Exam Ingestion & Review Studio")

    if not DATA_DIR.exists():
        st.warning(f"No ingestion data found at {DATA_DIR}. Please run the ingest pipeline first.")
        return

    # List available exam folders
    exam_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir()]
    if not exam_dirs:
        st.info("No exam datasets staged yet.")
        return

    exam_map = {d.name: d for d in sorted(exam_dirs)}
    selected_exam_name = st.sidebar.selectbox("Select Exam", list(exam_map.keys()))
    exam_dir = exam_map[selected_exam_name]

    questions, report = load_staged_data(exam_dir)
    if not questions:
        st.warning("No staged questions found in this folder.")
        return

    # Sidebar Metrics & Filters
    st.sidebar.markdown("---")
    st.sidebar.subheader("Exam Ingest Summary")
    st.sidebar.metric("Total Parsed", report.get("questions_parsed", len(questions)))
    st.sidebar.metric("Flagged", report.get("questions_flagged", 0))
    st.sidebar.metric("Approved", sum(1 for q in questions if q.get("approved")))
    st.sidebar.metric("Expected", report.get("expected_questions", 200))

    if report.get("anomalies"):
        st.sidebar.error("⚠️ Anomalies Detected:")
        for anom in report["anomalies"]:
            st.sidebar.write(f"- {anom}")

    filter_choice = st.sidebar.radio(
        "Filter Questions",
        ["All", "Flagged Only", "Unapproved Only", "Approved Only"]
    )

    filtered_indices = []
    for idx, q in enumerate(questions):
        if filter_choice == "Flagged Only" and not q.get("flags"):
            continue
        if filter_choice == "Unapproved Only" and q.get("approved"):
            continue
        if filter_choice == "Approved Only" and not q.get("approved"):
            continue
        filtered_indices.append(idx)

    if not filtered_indices:
        st.info(f"No questions match the filter '{filter_choice}'.")
        return

    q_idx = st.sidebar.selectbox(
        "Jump to Question",
        filtered_indices,
        format_func=lambda i: f"Q{questions[i]['q_no']} - {questions[i]['stem'][:35]}..."
    )

    q = questions[q_idx]

    # Two column layout: Page Image beside Parsed Question
    col_img, col_form = st.columns([1, 1])

    with col_img:
        st.subheader("Source Page Image")
        page_num = q.get("page_num", 1)
        img_candidates = [
            exam_dir / "pages" / f"clean_page_{page_num:03d}.png",
            exam_dir / "pages" / f"page_{page_num:03d}.png",
        ]
        img_found = False
        for img_p in img_candidates:
            if img_p.is_file():
                st.image(str(img_p), caption=f"Page {page_num}", use_container_width=True)
                img_found = True
                break
        if not img_found:
            st.info(f"Page image {page_num} not available on disk.")

    with col_form:
        st.subheader(f"Question Details: Q{q['q_no']}")

        if q.get("flags"):
            for flag in q["flags"]:
                st.warning(f"🚩 Flag: {flag}")

        approval_status = "✅ APPROVED" if q.get("approved") else "⏳ PENDING REVIEW"
        st.write(f"**Status:** {approval_status}")

        stem_input = st.text_area("Question Stem (Bangla/English)", value=q["stem"], height=100)

        options = q.get("options", ["", "", "", ""])
        while len(options) < 4:
            options.append("")

        c1, c2 = st.columns(2)
        with c1:
            opt0 = st.text_input("Option 1 (ক)", value=options[0])
            opt1 = st.text_input("Option 2 (খ)", value=options[1])
        with c2:
            opt2 = st.text_input("Option 3 (গ)", value=options[2])
            opt3 = st.text_input("Option 4 (ঘ)", value=options[3])

        current_correct = q.get("correct_index")
        correct_labels = ["None (Unresolved)", "0 - (ক)", "1 - (খ)", "2 - (গ)", "3 - (ঘ)"]
        default_choice_idx = 0 if current_correct is None else current_correct + 1
        sel_correct = st.selectbox("Official Answer Key", correct_labels, index=default_choice_idx)
        new_correct = None if sel_correct.startswith("None") else int(sel_correct[0])

        explanation_input = st.text_area("Explanation", value=q.get("explanation") or "")

        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("💾 Save Changes", use_container_width=True):
                q["stem"] = stem_input
                q["options"] = [opt0, opt1, opt2, opt3]
                q["correct_index"] = new_correct
                q["explanation"] = explanation_input
                save_staged_data(exam_dir, questions)
                st.success("Changes saved!")
                st.rerun()

        with btn_c2:
            if st.button("✅ Approve Question", type="primary", use_container_width=True):
                q["stem"] = stem_input
                q["options"] = [opt0, opt1, opt2, opt3]
                q["correct_index"] = new_correct
                q["explanation"] = explanation_input
                q["approved"] = True
                q["status"] = "verified"
                save_staged_data(exam_dir, questions)
                st.success("Question approved!")
                st.rerun()

    st.markdown("---")
    st.subheader("Database Insertion")
    st.write("Only approved questions will be saved to the database with `source_type='past'`.")
    if st.button("🚀 Insert Approved Questions to PostgreSQL"):
        try:
            inserted = insert_approved_to_db(questions)
            st.success(f"Successfully inserted {inserted} approved questions into the database!")
        except Exception as exc:
            st.error(f"Failed to insert into database: {exc}")


if __name__ == "__main__":
    main()
