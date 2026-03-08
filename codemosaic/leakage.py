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
        write_leakage_report(report, output_file)
    return report



def write_leakage_report(report: dict[str, object], output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return output_file



def has_leakage_budget(policy: MaskPolicy) -> bool:
    if policy.leakage.max_total_score is not None or policy.leakage.max_file_score is not None:
        return True
    return any(
        rule.max_total_score is not None or rule.max_file_score is not None for rule in policy.leakage.rules
    )



def evaluate_leakage_budget(report: dict[str, object], policy: MaskPolicy) -> dict[str, object] | None:
    if not has_leakage_budget(policy):
        return None

    files = report.get('files', [])
    file_items = [item for item in files if isinstance(item, dict)]
    violations: list[dict[str, object]] = []
    messages: list[str] = []

    total_score = int(report['summary']['total_score'])
    if policy.leakage.max_total_score is not None:
        passed = total_score <= policy.leakage.max_total_score
        if not passed:
            violations.append(
                {
                    'type': 'global_total',
                    'actual_score': total_score,
                    'max_allowed_score': policy.leakage.max_total_score,
                }
            )
            messages.append(
                f'global total leakage score {total_score} exceeds limit {policy.leakage.max_total_score}'
            )

    file_checks: list[dict[str, object]] = []
    for item in file_items:
        relative_path = str(item['path'])
        score = int(item['score'])
        effective = policy.resolve_leakage_file_policy(relative_path)
        if effective.max_file_score is None:
            continue
        passed = score <= effective.max_file_score
        check = {
            'path': relative_path,
            'actual_score': score,
            'max_allowed_score': effective.max_file_score,
            'matched_pattern': effective.matched_pattern,
            'passed': passed,
        }
        file_checks.append(check)
        if not passed:
            violations.append(
                {
                    'type': 'file_score',
                    'path': relative_path,
                    'actual_score': score,
                    'max_allowed_score': effective.max_file_score,
                    'matched_pattern': effective.matched_pattern,
                }
            )
            pattern_suffix = f" (rule: {effective.matched_pattern})" if effective.matched_pattern else ''
            messages.append(
                f'file leakage score {relative_path}={score} exceeds limit {effective.max_file_score}{pattern_suffix}'
            )

    rule_totals: list[dict[str, object]] = []
    for rule in policy.leakage.rules:
        if rule.max_total_score is None:
            continue
        matched_files = [item for item in file_items if _path_matches_rule(policy, str(item['path']), rule.pattern)]
        actual_total = int(sum(int(item['score']) for item in matched_files))
        passed = actual_total <= rule.max_total_score
        rule_summary = {
            'pattern': rule.pattern,
            'actual_score': actual_total,
            'max_allowed_score': rule.max_total_score,
            'matched_files': [str(item['path']) for item in matched_files],
            'passed': passed,
        }
        rule_totals.append(rule_summary)
        if not passed:
            violations.append(
                {
                    'type': 'rule_total',
                    'pattern': rule.pattern,
                    'actual_score': actual_total,
                    'max_allowed_score': rule.max_total_score,
                    'matched_files': rule_summary['matched_files'],
                }
            )
            messages.append(
                f'rule total leakage score {rule.pattern}={actual_total} exceeds limit {rule.max_total_score}'
            )

    return {
        'configured': True,
        'passed': not violations,
        'global_limits': {
            'max_total_score': policy.leakage.max_total_score,
            'max_file_score': policy.leakage.max_file_score,
        },
        'file_checks': file_checks,
        'rule_totals': rule_totals,
        'violations': violations,
        'messages': messages,
    }



def _path_matches_rule(policy: MaskPolicy, relative_path: str, pattern: str) -> bool:
    return any(rule.pattern == pattern for rule in policy.matching_leakage_rules(relative_path))



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
