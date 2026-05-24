"""Skills loader — injects markdown skill files into the system prompt."""

from __future__ import annotations

from pathlib import Path


def load_skills(skills_dir: Path) -> str:
    """Load all .md files from skills_dir and return combined text."""
    if not skills_dir.exists():
        return ""
    parts: list[str] = []
    for md_file in sorted(skills_dir.glob("*.md")):
        text = md_file.read_text(errors="replace").strip()
        if text:
            parts.append(f"### Skill: {md_file.stem}\n\n{text}")
    return "\n\n---\n\n".join(parts)
