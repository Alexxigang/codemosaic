from __future__ import annotations

from pathlib import Path

from codemosaic.workspace import DEFAULT_EXCLUDES, SUPPORTED_TEXT_EXTENSIONS, _matches


def build_markdown_bundle(
    source_root: Path,
    output_file: Path,
    max_files: int = 20,
    max_chars_per_file: int = 12000,
) -> Path:
    files = _collect_files(source_root, max_files=max_files)
    lines: list[str] = []
    lines.append("# AI Context Bundle")
    lines.append("")
    lines.append(f"- Source: `{source_root}`")
    lines.append(f"- Files: {len(files)}")
    lines.append("")
    lines.append("## Tree")
    lines.append("")
    for path in files:
        lines.append(f"- `{path.as_posix()}`")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    for relative_path in files:
        absolute_path = source_root / relative_path
        text = absolute_path.read_text(encoding="utf-8", errors="ignore")
        truncated = text[:max_chars_per_file]
        suffix = "\n... [truncated]" if len(text) > max_chars_per_file else ""
        language = _language_for(relative_path.suffix)
        lines.append(f"### `{relative_path.as_posix()}`")
        lines.append("")
        lines.append(f"```{language}")
        lines.append(truncated + suffix)
        lines.append("```")
        lines.append("")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def _collect_files(source_root: Path, max_files: int) -> list[Path]:
    items: list[Path] = []
    for path in sorted(source_root.rglob("*")):
        if len(items) >= max_files:
            break
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        relative_posix = relative.as_posix()
        if _matches(relative_posix, DEFAULT_EXCLUDES):
            continue
        if path.suffix not in SUPPORTED_TEXT_EXTENSIONS and path.name not in {"README.md", "policy.sample.yaml"}:
            continue
        items.append(relative)
    return items


def _language_for(extension: str) -> str:
    return {
        ".py": "python",
        ".ts": "ts",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(extension, "text")
