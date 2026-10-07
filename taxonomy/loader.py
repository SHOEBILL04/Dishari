"""Taxonomy loader and schema model for /taxonomy."""

from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field

DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parent / "bcs_topics.yaml"


class TopicNode(BaseModel):
    """Individual topic node in the hierarchy."""
    id: str
    subject_slug: str
    name_bn: str
    name_en: str
    level: int = 1
    parent_id: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)


class SubjectTaxonomy(BaseModel):
    """Subject level containing its allocated marks and child topics."""
    slug: str
    name_bn: str
    name_en: str
    marks: float
    topics: list[TopicNode] = Field(default_factory=list)


class SyllabusTaxonomy(BaseModel):
    """Complete syllabus version structure."""
    version_id: str
    name: str
    effective_from: str
    total_marks: float
    subjects: list[SubjectTaxonomy] = Field(default_factory=list)


def load_taxonomy(
    version: str = "bcs-35th-current",
    yaml_path: Optional[Path] = None,
) -> SyllabusTaxonomy:
    """Load and parse the BCS topics YAML file for a given syllabus version."""
    path = yaml_path or DEFAULT_TAXONOMY_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Taxonomy file not found at {path}")

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    versions = raw_data.get("syllabus_versions", {})

    if version not in versions:
        raise KeyError(
            f"Syllabus version '{version}' not found in {path.name}. Available: {list(versions.keys())}"
        )

    ver_data = versions[version]
    subjects_list = []

    for sub in ver_data.get("subjects", []):
        sub_slug = sub["slug"]
        topics_list = []
        for t in sub.get("topics", []):
            topics_list.append(
                TopicNode(
                    id=t["id"],
                    subject_slug=sub_slug,
                    name_bn=t["name_bn"],
                    name_en=t["name_en"],
                    level=t.get("level", 1),
                    parent_id=t.get("parent_id"),
                    keywords=t.get("keywords", []),
                )
            )
        subjects_list.append(
            SubjectTaxonomy(
                slug=sub_slug,
                name_bn=sub["name_bn"],
                name_en=sub["name_en"],
                marks=float(sub.get("marks", 0.0)),
                topics=topics_list,
            )
        )

    return SyllabusTaxonomy(
        version_id=version,
        name=ver_data.get("name", version),
        effective_from=ver_data.get("effective_from", "2014-01-01"),
        total_marks=float(ver_data.get("total_marks", 200.0)),
        subjects=subjects_list,
    )


def get_all_topics_dict(
    version: str = "bcs-35th-current",
    yaml_path: Optional[Path] = None,
) -> dict[str, TopicNode]:
    """Return dictionary mapping topic_id -> TopicNode."""
    tax = load_taxonomy(version=version, yaml_path=yaml_path)
    topic_map = {}
    for sub in tax.subjects:
        for t in sub.topics:
            topic_map[t.id] = t
    return topic_map


def format_candidate_topics_for_llm(
    candidate_ids: list[str],
    version: str = "bcs-35th-current",
    yaml_path: Optional[Path] = None,
) -> str:
    """Format the top candidate topics into a clean prompt block for prompt B4."""
    topics = get_all_topics_dict(version=version, yaml_path=yaml_path)
    lines = []
    for cid in candidate_ids:
        t = topics.get(cid)
        if t:
            kw_str = ", ".join(t.keywords[:8])
            lines.append(
                f"- ID: {t.id} | Subject: {t.subject_slug}\n"
                f"  Title: {t.name_bn} ({t.name_en})\n"
                f"  Keywords/Concepts: {kw_str}"
            )
        else:
            lines.append(f"- ID: {cid}")
    return "\n".join(lines)
