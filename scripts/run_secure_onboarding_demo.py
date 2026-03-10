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
    registry_path = workspace_root / '.codemosaic' / 'key-registry.json'
    run_audit_file = workspace_root / '.codemosaic' / 'run-audit.json'
    leakage_report_file = workspace_root / '.codemosaic' / 'leakage-report.json'

    before_state = summarize_workspace_state(workspace_root)

    setup_result = _capture_cli(
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
    mask_result = _capture_cli(
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
    write_leakage_report(leak, leakage_report_file)

    registry_entries = [entry.to_dict() for entry in load_key_registry(registry_path)]
    signing_key_id = next((entry['key_id'] for entry in registry_entries if entry['key_id'].endswith('-signing')), None)
    mapping_files = sorted((workspace_root / '.codemosaic' / 'runs').glob('*/mapping.enc.json'))
    mapping_file = mapping_files[-1] if mapping_files else None
    run_id = mapping_file.parent.name if mapping_file else None

    verify_result = None
    if mapping_file is not None and signing_key_id is not None:
        verify_result = _capture_cli(
            [
                'verify-mapping',
                str(mapping_file),
                '--signing-key-id',
                signing_key_id,
                '--signing-key-registry',
                str(registry_path),
                '--require-signature',
            ]
        )

    audit_runs_result = _capture_cli(
        [
            'audit-runs',
            str(workspace_root),
            '--signing-key-id',
            signing_key_id or f'{key_prefix}-signing',
            '--signing-key-registry',
            str(registry_path),
            '--output',
            str(run_audit_file),
        ]
    )
    run_audit_payload = json.loads(run_audit_file.read_text(encoding='utf-8')) if run_audit_file.exists() else {}
    audit_events = read_audit_events(workspace_root, limit=20)
    after_state = summarize_workspace_state(workspace_root)

    summary = {
        'workspace_root': str(workspace_root),
        'masked_root': str(masked_root),
        'policy_path': str(policy_path),
        'preset_id': preset_name,
        'registry_path': str(registry_path),
        'mapping_file': str(mapping_file) if mapping_file else None,
        'run_id': run_id,
        'leakage_report_file': str(leakage_report_file),
        'run_audit_file': str(run_audit_file),
        'leakage_budget': budget,
        'registry_entries': registry_entries,
        'audit_events': audit_events,
        'before_state': before_state,
        'after_state': after_state,
        'commands': {
            'setup_workspace': _format_cli_command([
                'python', '-m', 'codemosaic', 'setup-workspace', str(workspace_root), '--preset', preset_name, '--key-prefix', key_prefix
            ]),
            'mask': _format_cli_command([
                'python', '-m', 'codemosaic', 'mask', str(workspace_root), '--policy', str(policy_path), '--output', str(masked_root)
            ]),
            'verify_mapping': _format_cli_command([
                'python', '-m', 'codemosaic', 'verify-mapping', str(mapping_file), '--signing-key-id', signing_key_id or '<signing-key-id>', '--signing-key-registry', str(registry_path), '--require-signature'
            ]) if mapping_file else None,
            'audit_runs': _format_cli_command([
                'python', '-m', 'codemosaic', 'audit-runs', str(workspace_root), '--signing-key-id', signing_key_id or '<signing-key-id>', '--signing-key-registry', str(registry_path), '--output', str(run_audit_file)
            ]),
        },
        'setup_workspace_output': setup_result['stdout'],
        'mask_output': mask_result['stdout'],
        'verify_mapping_output': verify_result['stdout'] if verify_result else None,
        'run_audit_output': audit_runs_result['stdout'],
        'run_audit_summary': run_audit_payload.get('summary', {}),
        'created_files': [
            'policy.codemosaic.yaml',
            '.codemosaic/key-registry.json',
            *[f".codemosaic/keys/{Path(entry['reference']).name}" for entry in registry_entries],
            f".codemosaic/runs/{run_id}/mapping.enc.json" if run_id else '.codemosaic/runs/<run-id>/mapping.enc.json',
            '.codemosaic/leakage-report.json',
            '.codemosaic/run-audit.json',
        ],
    }
    summary_file = output_root / 'secure-onboarding-summary.json'
    summary['summary_file'] = str(summary_file)
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    write_markdown_summary(output_root / 'secure-onboarding-summary.md', summary)
    return summary


def summarize_workspace_state(workspace_root: Path) -> dict[str, object]:
    policy_file = workspace_root / 'policy.codemosaic.yaml'
    registry_file = workspace_root / '.codemosaic' / 'key-registry.json'
    key_dir = workspace_root / '.codemosaic' / 'keys'
    runs_root = workspace_root / '.codemosaic' / 'runs'
    audit_log = workspace_root / '.codemosaic' / 'audit-log.jsonl'
    key_files = sorted(key_dir.glob('*.key')) if key_dir.exists() else []
    encrypted_mappings = sorted(runs_root.glob('*/mapping.enc.json')) if runs_root.exists() else []
    return {
        'policy_ready': policy_file.exists(),
        'key_registry_present': registry_file.exists(),
        'managed_key_file_count': len(key_files),
        'encrypted_mapping_file_count': len(encrypted_mappings),
        'audit_log_present': audit_log.exists(),
    }


def write_markdown_summary(path: Path, summary: dict[str, object]) -> None:
    budget = summary.get('leakage_budget') or {}
    passed = budget.get('passed') if isinstance(budget, dict) else None
    leakage_status = 'passed' if passed else 'blocked'
    before_state = summary.get('before_state', {})
    after_state = summary.get('after_state', {})
    lines = [
        '# Secure Workspace Onboarding Demo',
        '',
        '## What changed',
        '',
        '| Capability | Before onboarding | After onboarding |',
        '| --- | --- | --- |',
        f"| Ready-to-use workspace policy | {'yes' if before_state.get('policy_ready') else 'no'} | {'yes' if after_state.get('policy_ready') else 'no'} |",
        f"| Local key registry | {'yes' if before_state.get('key_registry_present') else 'no'} | {'yes' if after_state.get('key_registry_present') else 'no'} |",
        f"| Managed key files | {before_state.get('managed_key_file_count', 0)} | {after_state.get('managed_key_file_count', 0)} |",
        f"| Encrypted mapping runs | {before_state.get('encrypted_mapping_file_count', 0)} | {after_state.get('encrypted_mapping_file_count', 0)} |",
        f"| Local audit trail | {'yes' if before_state.get('audit_log_present') else 'no'} | {'yes' if after_state.get('audit_log_present') else 'no'} |",
        '',
        '## Observable effect',
        '',
        f"- Workspace root: `{summary['workspace_root']}`",
        f"- Policy file: `{summary['policy_path']}`",
        f"- Encrypted mapping file: `{summary['mapping_file']}`",
        f"- Leakage gate status: `{leakage_status}`",
        f"- Run audit file: `{summary['run_audit_file']}`",
        '',
        '## Commands used in this demo',
        '',
        f"- Setup: `{summary['commands']['setup_workspace']}`",
        f"- Mask: `{summary['commands']['mask']}`",
        f"- Verify mapping: `{summary['commands']['verify_mapping']}`",
        f"- Audit runs: `{summary['commands']['audit_runs']}`",
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
        '## Run audit summary',
        '',
        f"- Summary: `{json.dumps(summary.get('run_audit_summary', {}), ensure_ascii=False)}`",
    ])
    verify_output = summary.get('verify_mapping_output')
    if verify_output:
        lines.extend([
            '',
            '## Verify mapping result',
            '',
            '```text',
            verify_output.strip(),
            '```',
        ])
    lines.extend([
        '',
        '## Recent audit events',
        '',
    ])
    for event in summary.get('audit_events', [])[:6]:
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


def _capture_cli(args: list[str]) -> dict[str, str]:
    result = subprocess.run(
        [sys.executable, '-m', 'codemosaic', *args],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {'stdout': result.stdout, 'stderr': result.stderr}


def _format_cli_command(parts: list[str | None]) -> str:
    return ' '.join(str(part) for part in parts if part)


if __name__ == '__main__':
    raise SystemExit(main())
