from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from codemosaic.policy import MaskPolicy
from codemosaic.workspace import DEFAULT_EXCLUDES, SUPPORTED_TEXT_EXTENSIONS, _matches


IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b")
STRING_RE = re.compile(r"(['\"])(.*?)(?<!\\)\1")
LINE_COMMENT_RE = re.compile(r"//\s*(.+)$", re.MULTILINE)
BLOCK_COMMENT_RE = re.compile(r"/\*\s*(.*?)\s*\*/", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"^(?:ID_\d{4}|COMMENT_\d{4}|STR_[A-Z]+_\d{4})$")
GENERIC_PATH_TERMS = {
    'src', 'lib', 'app', 'core', 'test', 'tests', 'spec', 'docs', 'web', 'api', 'pkg', 'cmd',
    'server', 'client', 'main', 'index', 'utils', 'util', 'common', 'shared', 'components',
    'hooks', 'pages', 'routes', 'service', 'services', 'models', 'types', 'examples'
}
GENERIC_IDENTIFIERS = {
    'value', 'data', 'items', 'result', 'request', 'response', 'config', 'options', 'message',
    'handler', 'service', 'controller', 'manager', 'client', 'server', 'provider', 'factory',
    'builder', 'context', 'payload', 'input', 'output', 'app', 'main', 'index', 'utils', 'test'
}


def leakage_report(
    source_root: Path,
    policy: MaskPolicy,
    output_file: Path | None = None,
) -> dict[str, object]:
    file_reports: list[dict[str, object]] = []
    totals: Counter[str] = Counter()
    for path in sorted(source_root.rglob('*')):
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
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        findings = analyze_masked_file(relative, text)
        totals.update(findings['counts'])
        file_reports.append(
            {
                'path': relative,
                'score': findings['score'],
                'risk': findings['risk'],
                'counts': dict(findings['counts']),
                'examples': findings['examples'],
            }
        )
    file_reports.sort(key=lambda item: (int(item['score']), item['path']), reverse=True)
    report = {
        'source_root': str(source_root),
        'summary': {
            'scanned_files': len(file_reports),
            'total_score': int(sum(int(item['score']) for item in file_reports)),
            'finding_counts': dict(totals),
            'highest_risk_files': [item['path'] for item in file_reports[:10] if item['score']],
        },
        'files': file_reports,
    }
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report



def analyze_masked_file(relative_path: str, text: str) -> dict[str, object]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = {
        'path_terms': [],
        'identifiers': [],
        'strings': [],
        'comments': [],
    }

    for term in extract_path_terms(relative_path):
        counts['path_terms'] += 1
        if len(examples['path_terms']) < 5:
            examples['path_terms'].append(term)

    for token in detect_unmasked_identifiers(text):
        counts['identifiers'] += 1
        if len(examples['identifiers']) < 5:
            examples['identifiers'].append(token)

    for literal in detect_unmasked_strings(text):
        counts['strings'] += 1
        if len(examples['strings']) < 5:
            examples['strings'].append(literal)

    for comment in detect_unmasked_comments(text):
        counts['comments'] += 1
        if len(examples['comments']) < 5:
            examples['comments'].append(comment)

    score = counts['path_terms'] * 3 + counts['identifiers'] * 2 + counts['strings'] * 2 + counts['comments'] * 4
    return {
        'counts': counts,
        'examples': examples,
        'score': int(score),
        'risk': classify_score(int(score)),
    }



def extract_path_terms(relative_path: str) -> list[str]:
    terms: list[str] = []
    parts = Path(relative_path).parts
    for part in parts:
        stem = Path(part).stem
        for token in re.split(r'[^A-Za-z0-9]+', stem):
            normalized = token.strip().lower()
            if not normalized or normalized in GENERIC_PATH_TERMS or normalized.isdigit():
                continue
            if PLACEHOLDER_RE.match(token):
                continue
            if len(normalized) < 4:
                continue
            terms.append(token)
    return terms



def detect_unmasked_identifiers(text: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for token in IDENTIFIER_RE.findall(text):
        normalized = token.lower()
        if token in seen:
            continue
        if PLACEHOLDER_RE.match(token):
            continue
        if normalized in GENERIC_IDENTIFIERS:
            continue
        if token.isupper() and len(token) <= 6:
            continue
        if re.fullmatch(r'[A-Z_]+', token) and token.startswith('STR_'):
            continue
        if normalized in {'true', 'false', 'null', 'none', 'self', 'cls', '__name__'}:
            continue
        seen.add(token)
        results.append(token)
    return results



def detect_unmasked_strings(text: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for _, literal in STRING_RE.findall(text):
        value = literal.strip()
        if not value or value in seen:
            continue
        if PLACEHOLDER_RE.match(value):
            continue
        if len(re.findall(r'[A-Za-z]', value)) < 4:
            continue
        seen.add(value)
        results.append(value)
    return results



def detect_unmasked_comments(text: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for body in LINE_COMMENT_RE.findall(text) + BLOCK_COMMENT_RE.findall(text):
        value = ' '.join(body.split())
        if not value or value in seen:
            continue
        if PLACEHOLDER_RE.match(value):
            continue
        seen.add(value)
        results.append(value)
    return results



def classify_score(score: int) -> str:
    if score >= 20:
        return 'high'
    if score >= 8:
        return 'medium'
    if score > 0:
        return 'low'
    return 'minimal'
