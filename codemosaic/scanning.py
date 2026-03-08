from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from codemosaic.policy import MaskPolicy
from codemosaic.workspace import DEFAULT_EXCLUDES, SUPPORTED_TEXT_EXTENSIONS, _matches


URL_RE = re.compile(r"https?://[^\s'\"`<>]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
PHONE_RE = re.compile(r"\b\+?[\d][\d\-\s()]{6,}\d\b")
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|passwd|password|client[_-]?secret|bearer\s+[A-Za-z0-9._\-]+)"
)
INTERNAL_HOST_RE = re.compile(r"\b(?:[A-Za-z0-9-]+\.)*(?:corp|internal|intra|svc|local)\b", re.IGNORECASE)
COMMENT_HINT_RE = re.compile(r"(?i)(todo|hack|temporary|internal|private|confidential)")


def scan_workspace(
    source_root: Path,
    policy: MaskPolicy,
    output_file: Path | None = None,
) -> dict[str, object]:
    file_reports: list[dict[str, object]] = []
    totals: Counter[str] = Counter()
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root).as_posix()
        if _matches(relative, DEFAULT_EXCLUDES | set(policy.paths.exclude)):
            continue
        if path.suffix not in SUPPORTED_TEXT_EXTENSIONS:
            continue
        if policy.paths.include and not _matches(relative, set(policy.paths.include)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings = _scan_text(text)
        totals.update(findings)
        file_reports.append(
            {
                "path": relative,
                "findings": dict(findings),
                "total_findings": int(sum(findings.values())),
                "size_chars": len(text),
            }
        )
    file_reports.sort(key=lambda item: int(item["total_findings"]), reverse=True)
    report = {
        "source_root": str(source_root),
        "summary": {
            "scanned_files": len(file_reports),
            "finding_counts": dict(totals),
            "highest_risk_files": [item["path"] for item in file_reports[:10] if item["total_findings"]],
        },
        "files": file_reports,
    }
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _scan_text(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    counts["urls"] = len(URL_RE.findall(text))
    counts["emails"] = len(EMAIL_RE.findall(text))
    counts["phones"] = len(PHONE_RE.findall(text))
    counts["secrets"] = len(SECRET_RE.findall(text))
    counts["internal_hosts"] = len(INTERNAL_HOST_RE.findall(text))
    counts["comment_hints"] = len(COMMENT_HINT_RE.findall(text))
    return counts
