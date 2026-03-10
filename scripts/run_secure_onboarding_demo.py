from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codemosaic.audit import read_audit_events
from codemosaic.key_management import load_key_registry
from codemosaic.leakage import evaluate_leakage_budget, leakage_report, write_leakage_report
from codemosaic.policy import load_policy

DEFAULT_SOURCE = ROOT / 'examples' / 'demo-repo'
DEFAULT_OUTPUT = ROOT / 'dist' / 'secure-onboarding-demo'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run a secure workspace onboarding demo for CodeMosaic.')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--preset', type=str, default='balanced-ai-gateway')
    parser.add_argument('--key-prefix', type=str, default='team-dev')
    parser.add_argument('--clean', action='store_true')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_secure_onboarding_demo(
        source_root=args.source.resolve(),
        output_root=args.output_root.resolve(),
        preset_name=args.preset,
        key_prefix=args.key_prefix,
        clean=args.clean,
    )
    print(summary['summary_file'])
    return 0


def run_secure_onboarding_demo(
    source_root: Path,
    output_root: Path,
    *,
    preset_name: str,
    key_prefix: str,
    clean: bool = False,
) -> dict[str, object]:
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    workspace_root = output_root / 'demo-repo'
    masked_root = output_root / 'demo-repo.masked'
    if workspace_root.exists():
        shutil.rmtree(workspace_root)
    if masked_root.exists():
        shutil.rmtree(masked_root)
    shutil.copytree(source_root, workspace_root)

    policy_path = workspace_root / 'policy.codemosaic.yaml'
    _run_cli(
        [
            'setup-workspace',
            str(workspace_root),
            '--preset',
            preset_name,
            '--key-prefix',
            key_prefix,
            '--policy-output',
            str(policy_path),
            '--force',
        ]
    )
    _run_cli(
        [
            'mask',
            str(workspace_root),
            '--policy',
            str(policy_path),
            '--output',
            str(masked_root),
        ]
    )

    policy = load_policy(policy_path)
    leak = leakage_report(masked_root, policy)
    budget = evaluate_leakage_budget(leak, policy)
    if budget is not None:
        leak['budget'] = budget
    leakage_report_file = workspace_root / '.codemosaic' / 'leakage-report.json'
    write_leakage_report(leak, leakage_report_file)

    registry_path = workspace_root / '.codemosaic' / 'key-registry.json'
    registry_entries = [entry.to_dict() for entry in load_key_registry(registry_path)]
    audit_events = read_audit_events(workspace_root, limit=20)
    mapping_files = sorted((workspace_root / '.codemosaic' / 'runs').glob('*/mapping.enc.json'))
    mapping_file = mapping_files[-1] if mapping_files else None
    run_id = mapping_file.parent.name if mapping_file else None
    summary = {
        'workspace_root': str(workspace_root),
        'masked_root': str(masked_root),
        'policy_path': str(policy_path),
        'preset_id': preset_name,
        'registry_path': str(registry_path),
        'mapping_file': str(mapping_file) if mapping_file else None,
        'run_id': run_id,
        'leakage_report_file': str(leakage_report_file),
        'leakage_budget': budget,
        'registry_entries': registry_entries,
        'audit_events': audit_events,
        'created_files': [
            'policy.codemosaic.yaml',
            '.codemosaic/key-registry.json',
            *[f".codemosaic/keys/{Path(entry['reference']).name}" for entry in registry_entries],
            f".codemosaic/runs/{run_id}/mapping.enc.json" if run_id else '.codemosaic/runs/<run-id>/mapping.enc.json',
            '.codemosaic/leakage-report.json',
        ],
    }
    summary_file = output_root / 'secure-onboarding-summary.json'
    summary['summary_file'] = str(summary_file)
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    write_markdown_summary(output_root / 'secure-onboarding-summary.md', summary)
    return summary


def write_markdown_summary(path: Path, summary: dict[str, object]) -> None:
    budget = summary.get('leakage_budget') or {}
    passed = budget.get('passed') if isinstance(budget, dict) else None
    leakage_status = 'passed' if passed else 'blocked'
    lines = [
        '# Secure Workspace Onboarding Demo',
        '',
        '## What happened',
        '',
        f"- Workspace root: `{summary['workspace_root']}`",
        f"- Policy file: `{summary['policy_path']}`",
        f"- Key registry: `{summary['registry_path']}`",
        f"- Encrypted mapping file: `{summary['mapping_file']}`",
        f"- Leakage gate status: `{leakage_status}`",
        '',
        '## Files created by onboarding',
        '',
    ]
    for item in summary.get('created_files', []):
        lines.append(f'- `{item}`')
    lines.extend([
        '',
        '## Registry entries',
        '',
    ])
    for entry in summary.get('registry_entries', []):
        lines.append(f"- `{entry['key_id']}` -> {entry['source']}:{entry['reference']} ({entry['status']})")
    lines.extend([
        '',
        '## Recent audit events',
        '',
    ])
    for event in summary.get('audit_events', [])[:5]:
        lines.append(f"- `{event['action']}` at `{event['event_time']}`")
    lines.extend([
        '',
        '## Why this matters',
        '',
        '- The workspace policy is immediately usable for `mask` without extra key flags.',
        '- Mapping files are encrypted by default because the generated policy points at the local registry.',
        '- Signing metadata is ready for `verify-mapping`, `audit-runs`, and guarded `unmask-patch` flows.',
    ])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def _run_cli(args: list[str]) -> None:
    subprocess.run(
        [sys.executable, '-m', 'codemosaic', *args],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


if __name__ == '__main__':
    raise SystemExit(main())
