"""Generates docs/configuration.md from .env.example.

Run via: make docs-env
Invoked automatically by the pre-commit docs-env hook when .env.example changes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ENV_EXAMPLE = Path(".env.example")
OUTPUT = Path("docs/configuration.md")

SECTION_RE = re.compile(r"^#\s*──+\s*(.+?)\s*──+")


def parse_env(text: str) -> list[dict]:
    """Parse .env.example into structured sections with variables."""
    sections: list[dict] = []
    current_section = {"heading": "General", "vars": []}
    pending_comment: list[str] = []

    for line in text.splitlines():
        line = line.rstrip()

        # Section header: # ── Heading ──────
        m = SECTION_RE.match(line)
        if m:
            if current_section["vars"] or pending_comment:
                sections.append(current_section)
            current_section = {"heading": m.group(1).strip(), "vars": []}
            pending_comment = []
            continue

        # Comment line (not a section header)
        if line.startswith("#"):
            text_part = line.lstrip("#").strip()
            if text_part:
                pending_comment.append(text_part)
            continue

        # Blank line resets pending comment
        if not line:
            pending_comment = []
            continue

        # KEY=value
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            description = " ".join(pending_comment)
            pending_comment = []
            current_section["vars"].append(
                {
                    "key": key,
                    "default": value or "—",
                    "description": description,
                }
            )

    if current_section["vars"]:
        sections.append(current_section)

    return sections


def render_markdown(sections: list[dict]) -> str:
    lines = [
        "# Configuration",
        "",
        "> Auto-generated from `.env.example` by `make docs-env`.",
        "> Do not edit by hand — run `make docs-env` to regenerate.",
        "",
    ]

    for section in sections:
        if not section["vars"]:
            continue
        lines.append(f"## {section['heading']}")
        lines.append("")
        lines.append("| Variable | Default | Description |")
        lines.append("|---|---|---|")
        for var in section["vars"]:
            desc = var["description"].replace("|", "\\|") if var["description"] else ""
            default = f"`{var['default']}`" if var["default"] != "—" else "—"
            lines.append(f"| `{var['key']}` | {default} | {desc} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    if not ENV_EXAMPLE.exists():
        print(f"ERROR: {ENV_EXAMPLE} not found", file=sys.stderr)
        sys.exit(1)

    sections = parse_env(ENV_EXAMPLE.read_text())
    md = render_markdown(sections)
    OUTPUT.write_text(md)
    print(f"Generated {OUTPUT} ({len(sections)} sections, "
          f"{sum(len(s['vars']) for s in sections)} variables)")


if __name__ == "__main__":
    main()
