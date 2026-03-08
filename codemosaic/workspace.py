from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from codemosaic.crypto import DEFAULT_PROVIDER_ID
from codemosaic.mapping import MappingVault
from codemosaic.maskers import mask_jsts_source, mask_python_text, mask_text_source
from codemosaic.maskers.jsts_masker import JS_TS_EXTENSIONS
from codemosaic.models import FileReport, RunReport
from codemosaic.policy import EffectiveMappingPolicy, MaskPolicy


SUPPORTED_TEXT_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs'}
DEFAULT_EXCLUDES = {
    '.git/**',
    '.codemosaic/**',
    'node_modules/**',
    'dist/**',
    'build/**',
    'coverage/**',
    '__pycache__/**',
}


def mask_workspace(
    source_root: Path,
    output_root: Path,
    policy: MaskPolicy,
    run_id: str | None = None,
    mapping_passphrase: str | None = None,
    mapping_encryption_provider: str | None = None,
) -> RunReport:
    effective_mapping = resolve_workspace_mapping_policy(
        source_root,
        output_root,
        policy,
        encryption_requested=bool(mapping_passphrase),
        provider_override=mapping_encryption_provider,
    )
    if effective_mapping.require_encryption and not mapping_passphrase:
        raise ValueError('policy requires encrypted mapping; provide --passphrase-env or --passphrase-file')
    selected_provider = effective_mapping.encryption_provider or DEFAULT_PROVIDER_ID
    run_name = run_id or datetime.now().strftime('%Y%m%d-%H%M%S')
    vault = MappingVault()
    files: list[FileReport] = []
    totals: Counter[str] = Counter()
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = source_root / '.codemosaic' / 'runs' / run_name
    mapping_name = 'mapping.enc.json' if mapping_passphrase else 'mapping.json'
    mapping_path = run_dir / mapping_name
    report_path = run_dir / 'report.json'
    for path in sorted(source_root.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root).as_posix()
        if _is_under_output(path, output_root) or _matches(relative, DEFAULT_EXCLUDES | set(policy.paths.exclude)):
            continue
        action = 'skipped'
        masker = 'none'
        stats: dict[str, int] = {}
        if _should_process(relative, path, policy):
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                if policy.workspace.copy_unmatched:
                    destination = output_root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
                    action = 'copied'
                files.append(FileReport(relative, action, masker, stats))
                continue
            if path.suffix == '.py':
                masked, stats = mask_python_text(text, vault, policy)
                masker = 'python'
            elif path.suffix in JS_TS_EXTENSIONS:
                masked, stats = mask_jsts_source(text, vault, policy)
                masker = 'jsts'
            else:
                masked, stats = mask_text_source(text, vault, policy)
                masker = 'text'
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(masked, encoding='utf-8')
            action = 'masked'
            totals.update(stats)
        elif policy.workspace.copy_unmatched:
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            action = 'copied'
        files.append(FileReport(relative, action, masker, stats))
    metadata = {
        'run_id': run_name,
        'source_root': str(source_root),
        'output_root': str(output_root),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'encrypted': bool(mapping_passphrase),
        'encryption_provider': selected_provider if mapping_passphrase else None,
        'policy_require_encryption': effective_mapping.require_encryption,
        'policy_matched_mapping_rules': list(effective_mapping.matched_patterns),
    }
    vault.save(
        mapping_path,
        metadata=metadata,
        passphrase=mapping_passphrase,
        encryption_provider=selected_provider,
    )
    report = RunReport(
        run_id=run_name,
        source_root=str(source_root),
        output_root=str(output_root),
        mapping_file=str(mapping_path),
        files=files,
        totals=dict(totals),
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')
    return report



def resolve_workspace_mapping_policy(
    source_root: Path,
    output_root: Path,
    policy: MaskPolicy,
    encryption_requested: bool,
    provider_override: str | None,
) -> EffectiveMappingPolicy:
    relative_paths = collect_maskable_relative_paths(source_root, output_root, policy)
    return policy.resolve_mapping_policy(
        relative_paths,
        encryption_requested=encryption_requested,
        provider_override=provider_override,
    )



def collect_maskable_relative_paths(source_root: Path, output_root: Path, policy: MaskPolicy) -> list[str]:
    relative_paths: list[str] = []
    for path in sorted(source_root.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root).as_posix()
        if _is_under_output(path, output_root) or _matches(relative, DEFAULT_EXCLUDES | set(policy.paths.exclude)):
            continue
        if _should_process(relative, path, policy):
            relative_paths.append(relative)
    return relative_paths



def _should_process(relative: str, path: Path, policy: MaskPolicy) -> bool:
    if path.suffix not in SUPPORTED_TEXT_EXTENSIONS:
        return False
    if policy.paths.include:
        return _matches(relative, set(policy.paths.include))
    return True



def _matches(relative: str, patterns: set[str]) -> bool:
    return any(
        fnmatch(relative, pattern)
        or fnmatch(f'./{relative}', pattern)
        or ('/' not in pattern and fnmatch(Path(relative).name, pattern))
        for pattern in patterns
    )



def _is_under_output(path: Path, output_root: Path) -> bool:
    try:
        path.relative_to(output_root)
        return True
    except ValueError:
        return False
