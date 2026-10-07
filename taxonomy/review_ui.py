"""Streamlit review UI for the needs_review taxonomy queue with keyboard shortcuts."""

import json
from pathlib import Path
import os
import streamlit as st
import streamlit.components.v1 as components

from taxonomy.loader import get_all_topics_dict

QUEUE_FILE = Path(__file__).resolve().parent.parent / "data" / "taxonomy_review_queue.json"


def load_review_queue() -> list[dict]:
    """Load pending review queue from disk or create mock items if empty."""
    if QUEUE_FILE.is_file():
        try:
            return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Starter review queue demo if empty
    starter = [
        {
            "id": "rev_001",
            "stem": "কোন গ্রন্থটি আলাওলের রচনা?",
            "options": ["পদ্মাবতী", "মধুমালতী", "ইউসুফ-জোলেখা", "সতীময়না"],
            "predicted_topic_id": "top_bn_lit_medieval",
            "confidence": 0.74,
            "candidates": [
                {"id": "top_bn_lit_medieval", "title": "মধ্যযুগীয় সাহিত্য", "sim": 0.74},
                {"id": "top_bn_lit_ancient", "title": "প্রাচীন যুগ (চর্যাপদ)", "sim": 0.69},
                {"id": "top_bn_lit_modern", "title": "আধুনিক যুগ ও সাহিত্যিকবৃন্দ", "sim": 0.45},
                {"id": "top_bn_gram_etymology", "title": "শব্দ ও পদ প্রকরণ", "sim": 0.30},
                {"id": "top_bn_gram_sandhi", "title": "সন্ধি", "sim": 0.22},
            ],
            "reasoning": "Top 2 candidates (medieval vs ancient) are within 0.05 margin.",
            "reviewed": False,
        },
        {
            "id": "rev_002",
            "stem": "Which clause is present in: 'I know where he lives'?",
            "options": ["Noun clause", "Adverb clause", "Adjective clause", "Coordinate clause"],
            "predicted_topic_id": "top_en_clause_transformation",
            "confidence": 0.71,
            "candidates": [
                {"id": "top_en_clause_transformation", "title": "Clauses, Voice & Narration", "sim": 0.71},
                {"id": "top_en_parts_of_speech", "title": "Parts of Speech & Syntax", "sim": 0.68},
                {"id": "top_en_vocab_idioms", "title": "Vocabulary, Synonyms & Idioms", "sim": 0.40},
                {"id": "top_en_lit_renaissance", "title": "Elizabethan Literature", "sim": 0.20},
                {"id": "top_en_lit_modern", "title": "Modern Literature", "sim": 0.15},
            ],
            "reasoning": "Ambiguous boundary between Parts of Speech and Clause syntax.",
            "reviewed": False,
        }
    ]
    save_review_queue(starter)
    return starter


def save_review_queue(items: list[dict]) -> None:
    """Save review queue back to disk."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_decision_to_db(question_id: str, topic_id: str, confidence: float, db_url: str = None) -> bool:
    """Update topic_id in Postgres questions table and record in tag_log."""
    try:
        import psycopg
        url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dishari")
        with psycopg.connect(url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tag_log (
                        question_id, model, topic_id, confidence, reviewed_by_human
                    ) VALUES (%s, 'human_reviewer', %s, %s, true);
                    """,
                    (question_id, topic_id, confidence)
                )
                cur.execute(
                    """
                    UPDATE questions
                    SET topic_id = %s, status = 'verified'
                    WHERE id = %s;
                    """,
                    (topic_id, question_id)
                )
        return True
    except Exception:
        return False


def main():
    st.set_page_config(page_title="Dishari - Taxonomy Review Queue", layout="wide")
    st.title("Dishari: Needs-Review Queue (Taxonomy Studio)")

    queue = load_review_queue()
    pending = [q for q in queue if not q.get("reviewed")]

    st.sidebar.header("Queue Summary")
    st.sidebar.metric("Pending Reviews", len(pending))
    st.sidebar.metric("Total in Queue", len(queue))
    st.sidebar.markdown("---")
    st.sidebar.subheader("Keyboard Shortcuts")
    st.sidebar.info(
        """
        - **1, 2, 3, 4, 5**: Select Candidate 1 to 5
        - **A** or **Enter**: Approve Selection
        - **R**: Reject / Flag
        - **N**: Next Question
        """
    )

    if not pending:
        st.success("🎉 All questions in the review queue have been verified!")
        if st.button("Reset Demo Queue"):
            for q in queue:
                q["reviewed"] = False
            save_review_queue(queue)
            st.rerun()
        return

    # Current item
    curr_idx = st.session_state.get("review_idx", 0)
    if curr_idx >= len(pending):
        curr_idx = 0
        st.session_state["review_idx"] = 0

    item = pending[curr_idx]

    # Embedded Javascript for keyboard shortcuts
    components.html(
        """
        <script>
        const doc = window.parent.document;
        doc.addEventListener('keydown', function(e) {
            // Ignore if active element is an input or textarea
            const activeTag = doc.activeElement ? doc.activeElement.tagName.toLowerCase() : '';
            if (activeTag === 'input' || activeTag === 'textarea') return;

            const key = e.key.toLowerCase();
            const buttons = Array.from(doc.querySelectorAll('button'));

            if (['1', '2', '3', '4', '5'].includes(key)) {
                const targetText = '[' + key + ']';
                const candBtn = buttons.find(b => b.textContent && b.textContent.includes(targetText));
                if (candBtn) {
                    candBtn.click();
                    e.preventDefault();
                }
            } else if (key === 'a' || e.key === 'Enter') {
                const approveBtn = buttons.find(b => b.textContent && b.textContent.includes('Approve'));
                if (approveBtn) {
                    approveBtn.click();
                    e.preventDefault();
                }
            } else if (key === 'n') {
                const nextBtn = buttons.find(b => b.textContent && b.textContent.includes('Next'));
                if (nextBtn) {
                    nextBtn.click();
                    e.preventDefault();
                }
            }
        });
        </script>
        """,
        height=0,
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Question to Classify")
        st.markdown(f"**ID:** `{item['id']}`")
        st.info(f"### {item['stem']}")

        st.markdown("**Options:**")
        opts = item.get("options", [])
        for i, opt in enumerate(opts, start=1):
            st.write(f"- ({i}) {opt}")

        st.markdown("---")
        st.markdown("**Model Diagnostic Reasoning:**")
        st.write(item.get("reasoning", "Low confidence margin between top-2 candidates."))

    with col2:
        st.subheader("Candidate Topic Assignments")
        conf = item["confidence"]
        conf_pct = int(conf * 100)
        st.progress(conf)
        st.caption(f"Model Confidence: **{conf_pct}%** (Threshold: 80%)")

        candidates = item.get("candidates", [])
        chosen_topic_id = st.session_state.get("selected_topic", item["predicted_topic_id"])

        for idx, cand in enumerate(candidates, start=1):
            cid = cand["id"]
            title = cand.get("title", cid)
            sim = cand.get("sim", 0.0)
            is_selected = (chosen_topic_id == cid)

            btn_label = f"[{idx}] {title} (Sim: {sim:.2f}) {' ⭐ SELECTED' if is_selected else ''}"
            if st.button(btn_label, key=f"btn_cand_{idx}", use_container_width=True):
                chosen_topic_id = cid
                st.session_state["selected_topic"] = cid
                st.rerun()

        st.markdown("---")
        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("✅ Approve & Save (A / Enter)", type="primary", use_container_width=True):
                item["reviewed"] = True
                item["final_topic_id"] = chosen_topic_id
                save_review_queue(queue)
                sync_decision_to_db(item["id"], chosen_topic_id, 1.0)
                st.success(f"Assigned to {chosen_topic_id}!")
                st.rerun()

        with action_col2:
            if st.button("⏭️ Next / Skip (N)", use_container_width=True):
                st.session_state["review_idx"] = (curr_idx + 1) % len(pending)
                st.rerun()


if __name__ == "__main__":
    main()
