from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DEFAULT_GITATTRIBUTES = """* text=auto eol=lf
*.bat text eol=crlf
*.ps1 text eol=crlf
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.svg text eol=lf
*.vsix binary
"""

DEFAULT_RELEASE_CHECKLIST = """# Release Checklist

- [ ] Run `python -m unittest discover -s tests -v`
- [ ] Run `node --check extensions/vscode/extension.js`
- [ ] Run `python scripts/package_vscode_extension.py --overwrite`
- [ ] Install `dist/*.vsix` locally and smoke test VS Code commands
- [ ] Review `README.md`, `extensions/vscode/README.md`, and `docs/vscode-extension.md`
- [ ] Tag release with `v<version>`
- [ ] Confirm GitHub Actions uploaded the VSIX artifact
- [ ] Publish GitHub Release notes
"""

DEFAULT_RELEASE_NOTES = """# Release Notes Template

## Highlights

- CLI improvements:
- Security/privacy improvements:
- VS Code extension improvements:

## Included Capabilities

- Scan workspace for likely sensitive content
- Mask Python and JS/TS source before sharing with external AI tools
- Save mapping files locally, with optional passphrase protection
- Export AI bundles and translate masked patches back to original code
- Use the VS Code prototype extension with runs explorer and quick workflow

## Validation

- `python -m unittest discover -s tests -v`
- `python scripts/package_vscode_extension.py --overwrite`
- `node --check extensions/vscode/extension.js`

## Known Limitations

- No TypeScript AST masking yet
- Mapping encryption is still a standard-library prototype
- VS Code extension is still a prototype and not marketplace-published
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare repository metadata and release helper files.")
    parser.add_argument("--target-root", type=Path, default=Path.cwd())
    parser.add_argument("--init-git", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bootstrap_repository(args.target_root.resolve(), init_git=args.init_git)
    return 0


def bootstrap_repository(target_root: Path, init_git: bool = False) -> None:
    ensure_file_contains(target_root / '.gitattributes', DEFAULT_GITATTRIBUTES)
    ensure_file_contains(target_root / '.gitignore', 'dist/\n.vscode/\n')
    ensure_file(target_root / 'RELEASE_CHECKLIST.md', DEFAULT_RELEASE_CHECKLIST)
    ensure_file(target_root / '.github' / 'RELEASE_TEMPLATE.md', DEFAULT_RELEASE_NOTES)
    ensure_file(
        target_root / '.github' / 'ISSUE_TEMPLATE' / 'bug_report.md',
        BUG_REPORT_TEMPLATE,
    )
    ensure_file(
        target_root / '.github' / 'ISSUE_TEMPLATE' / 'feature_request.md',
        FEATURE_REQUEST_TEMPLATE,
    )
    if init_git and not (target_root / '.git').exists():
        subprocess.run(['git', 'init', str(target_root)], check=True, capture_output=True, text=True)


def ensure_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding='utf-8', newline='\n')


def ensure_file_contains(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding='utf-8') if path.exists() else ''
    missing_lines = [line for line in content.splitlines() if line and line not in existing]
    if not missing_lines:
        return
    joined = existing
    if joined and not joined.endswith('\n'):
        joined += '\n'
    joined += '\n'.join(missing_lines) + '\n'
    path.write_text(joined, encoding='utf-8', newline='\n')


BUG_REPORT_TEMPLATE = """---
name: Bug report
about: Report a bug in the CLI or VS Code prototype
---

## What happened

## Expected behavior

## Reproduction steps

## Environment

- OS:
- Python:
- VS Code:
- CodeMosaic version:
"""


FEATURE_REQUEST_TEMPLATE = """---
name: Feature request
about: Suggest an improvement for the CLI or VS Code prototype
---

## Problem to solve

## Proposed solution

## Alternatives considered

## Additional context
"""


if __name__ == '__main__':
    raise SystemExit(main())
