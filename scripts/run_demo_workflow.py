from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codemosaic.bundles import build_markdown_bundle
from codemosaic.leakage import evaluate_leakage_budget, leakage_report, write_leakage_report
from codemosaic.policy import load_policy
from codemosaic.scanning import scan_workspace
from codemosaic.workspace import mask_workspace

DEFAULT_SOURCE = ROOT / 'examples' / 'demo-repo'
DEFAULT_OUTPUT = ROOT / 'dist' / 'demo-output'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run a complete CodeMosaic demo workflow on the sample repository.')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--encrypt-mapping', action='store_true')
    parser.add_argument('--passphrase', type=str, default='demo-passphrase')
    parser.add_argument('--clean', action='store_true')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = args.source.resolve()
    output_root = args.output_root.resolve()
    run_demo_workflow(
        source_root=source,
        output_root=output_root,
        encrypt_mapping=args.encrypt_mapping,
        passphrase=args.passphrase if args.encrypt_mapping else None,
        clean=args.clean,
    )
    print(output_root)
    return 0


def run_demo_workflow(
    source_root: Path,
    output_root: Path,
    encrypt_mapping: bool = False,
    passphrase: str | None = None,
    clean: bool = False,
) -> dict[str, object]:
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    demo_repo = output_root / 'demo-repo'
    masked_repo = output_root / 'demo-repo.masked'
    if demo_repo.exists():
        shutil.rmtree(demo_repo)
    if masked_repo.exists():
        shutil.rmtree(masked_repo)
    shutil.copytree(source_root, demo_repo)

    policy_file = demo_repo / 'policy.yaml'
    policy = load_policy(policy_file)

    scan_report_file = demo_repo / '.codemosaic' / 'scan-report.json'
    leakage_report_file = demo_repo / '.codemosaic' / 'leakage-report.json'
    bundle_file = demo_repo / '.codemosaic' / 'ai-bundle.md'
    safe_bundle_file = demo_repo / '.codemosaic' / 'ai-bundle.safe.md'

    scan_report = scan_workspace(demo_repo, policy, output_file=scan_report_file)
    mask_report = mask_workspace(
        demo_repo,
        masked_repo,
        policy,
        run_id='demo',
        mapping_passphrase=passphrase if encrypt_mapping else None,
    )
    leakage = leakage_report(masked_repo, policy)
    budget = evaluate_leakage_budget(leakage, policy)
    if budget is not None:
        leakage['budget'] = budget
    write_leakage_report(leakage, leakage_report_file)

    build_markdown_bundle(masked_repo, bundle_file, max_files=10, max_chars_per_file=4000)
    safe_export = {
        'enabled': budget is not None,
        'status': 'not_configured',
        'report_file': str(leakage_report_file),
        'bundle_file': None,
        'messages': [],
    }
    if budget is not None:
        safe_export['messages'] = list(budget.get('messages', []))
        if budget.get('passed'):
            build_markdown_bundle(masked_repo, safe_bundle_file, max_files=10, max_chars_per_file=4000)
            safe_export['status'] = 'passed'
            safe_export['bundle_file'] = str(safe_bundle_file)
        else:
            safe_export['status'] = 'blocked'

    summary = {
        'source_root': str(demo_repo),
        'masked_root': str(masked_repo),
        'scan_report_file': str(scan_report_file),
        'leakage_report_file': str(leakage_report_file),
        'bundle_file': str(bundle_file),
        'mapping_file': mask_report.mapping_file,
        'run_id': mask_report.run_id,
        'stats': mask_report.totals,
        'scan_summary': scan_report['summary'],
        'leakage_summary': leakage['summary'],
        'safe_export': safe_export,
    }
    summary_file = output_root / 'demo-summary.json'
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    write_demo_markdown(output_root / 'demo-summary.md', summary)
    return summary


def write_demo_markdown(path: Path, summary: dict[str, object]) -> None:
    lines = [
        '# Demo Summary',
        '',
        f"- Source root: `{summary['source_root']}`",
        f"- Masked root: `{summary['masked_root']}`",
        f"- Mapping file: `{summary['mapping_file']}`",
        f"- Bundle file: `{summary['bundle_file']}`",
        f"- Leakage report: `{summary['leakage_report_file']}`",
        '',
        '## Scan Summary',
        '',
    ]
    scan_summary = summary['scan_summary']
    if isinstance(scan_summary, dict):
        lines.append(f"- Scanned files: {scan_summary.get('scanned_files', 0)}")
        lines.append(f"- Finding counts: `{json.dumps(scan_summary.get('finding_counts', {}), ensure_ascii=False)}`")
        highest = scan_summary.get('highest_risk_files', [])
        if highest:
            lines.append(f"- Highest-risk files: `{', '.join(highest)}`")

    leakage_summary = summary.get('leakage_summary', {})
    if isinstance(leakage_summary, dict):
        lines.extend([
            '',
            '## Leakage Summary',
            '',
            f"- Total leakage score: {leakage_summary.get('total_score', 0)}",
            f"- Highest-risk masked files: `{', '.join(leakage_summary.get('highest_risk_files', []))}`",
        ])

    safe_export = summary.get('safe_export', {})
    if isinstance(safe_export, dict):
        lines.extend([
            '',
            '## Safe Export Gate',
            '',
            f"- Status: `{safe_export.get('status', 'unknown')}`",
            f"- Leakage report: `{safe_export.get('report_file', '')}`",
        ])
        if safe_export.get('bundle_file'):
            lines.append(f"- Safe bundle: `{safe_export['bundle_file']}`")
        messages = safe_export.get('messages', [])
        if messages:
            lines.append(f"- Gate reasons: `{'; '.join(messages)}`")

    lines.extend([
        '',
        '## Mask Summary',
        '',
        f"- Run id: `{summary['run_id']}`",
        f"- Stats: `{json.dumps(summary['stats'], ensure_ascii=False)}`",
        '',
        '## Suggested Demo Flow',
        '',
        '1. Open the demo repo in VS Code',
        '2. Run `CodeMosaic: Quick Workflow`',
        '3. Open the latest scan report and leakage report',
        '4. Show that a regular bundle can be created from the masked workspace',
        '5. Run `CodeMosaic: Safe Export Bundle` and explain why the gate blocks or allows export',
        '6. Open the Runs view and highlight the leakage gate status item',
    ])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    raise SystemExit(main())
