"""Prompt loader for Dishari.

Loads markdown prompt templates from /prompts/*.md, parses version headers,
and interpolates variables into the prompt body.
"""

from pathlib import Path
from typing import Any
import yaml
from llm.types import PromptNotFoundError, PromptTemplate

DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(
    prompt_name: str, 
    variables: dict[str, Any], 
    prompts_dir: Path = DEFAULT_PROMPTS_DIR
) -> PromptTemplate:
    """Load a markdown prompt file, parse its header, and fill in variables.
    
    Args:
        prompt_name: Name of the prompt file (with or without .md extension).
        variables: Dictionary of replacement variables for template placeholders.
        prompts_dir: Directory containing prompt markdown files.
        
    Returns:
        PromptTemplate containing version metadata, system prompt, and rendered body.
        
    Raises:
        PromptNotFoundError: If the prompt markdown file does not exist.
        ValueError: If a required placeholder variable is missing from variables.
    """
    clean_name = prompt_name[:-3] if prompt_name.endswith(".md") else prompt_name
    file_path = prompts_dir / f"{clean_name}.md"

    if not file_path.is_file():
        raise PromptNotFoundError(
            f"Prompt template '{clean_name}.md' not found in {prompts_dir}"
        )

    raw_content = file_path.read_text(encoding="utf-8")

    # Parse YAML frontmatter header
    version = "1.0.0"
    description = ""
    system_prompt = None
    template_text = raw_content

    if raw_content.startswith("---"):
        parts = raw_content.split("---", 2)
        if len(parts) >= 3:
            header_yaml = parts[1].strip()
            template_text = parts[2].strip()
            try:
                metadata = yaml.safe_load(header_yaml) or {}
                version = str(metadata.get("version", "1.0.0"))
                description = str(metadata.get("description", ""))
                system_prompt = metadata.get("system")
                if system_prompt is not None:
                    system_prompt = str(system_prompt).strip()
            except Exception as exc:
                raise ValueError(f"Failed to parse frontmatter in {file_path.name}: {exc}")

    # Interpolate variables safely
    # Format non-string types (lists, dicts) cleanly as strings
    safe_vars = {}
    for key, val in variables.items():
        if isinstance(val, (dict, list)):
            import json
            safe_vars[key] = json.dumps(val, ensure_ascii=False, indent=2)
        else:
            safe_vars[key] = str(val)

    try:
        rendered_text = template_text.format(**safe_vars)
    except KeyError as missing_key:
        raise ValueError(
            f"Prompt '{clean_name}' requires variable {{{missing_key}}}, but it was not provided."
        )

    return PromptTemplate(
        name=clean_name,
        version=version,
        description=description,
        system_prompt=system_prompt,
        template_text=template_text,
        rendered_text=rendered_text,
    )
