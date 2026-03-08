from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from codemosaic.bundles import build_markdown_bundle
from codemosaic.crypto import describe_mapping_crypto_providers
from codemosaic.leakage import evaluate_leakage_budget, has_leakage_budget, leakage_report, write_leakage_report
from codemosaic.mapping import rewrap_mapping_file
from codemosaic.patching import apply_patch_file, translate_patch_file
from codemosaic.policy import load_policy
from codemosaic.runs import rekey_run_mappings
from codemosaic.scanning import scan_workspace
from codemosaic.segmentation import mask_segmented_workspace, plan_mask_segments, write_segment_plan
from codemosaic.workspace import mask_workspace


LEAKAGE_BUDGET_EXIT_CODE = 3



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='codemosaic')
    subparsers = parser.add_subparsers(dest='command', required=True)

    mask_parser = subparsers.add_parser('mask', help='Generate a masked workspace')
    mask_parser.add_argument('source', type=Path)
    mask_parser.add_argument('--policy', type=Path, default=None)
    mask_parser.add_argument('--output', type=Path, default=None)
    mask_parser.add_argument('--run-id', type=str, default=None)
    mask_parser.add_argument('--encrypt-mapping', action='store_true')
    mask_parser.add_argument('--encryption-provider', type=str, default=None)
    _add_passphrase_arguments(mask_parser)

    segmented_parser = subparsers.add_parser('mask-segmented', help='Generate multiple masked workspaces grouped by policy segments')
    segmented_parser.add_argument('source', type=Path)
    segmented_parser.add_argument('--policy', type=Path, default=None)
    segmented_parser.add_argument('--output', type=Path, default=None)
    segmented_parser.add_argument('--run-id-prefix', type=str, default=None)
    segmented_parser.add_argument('--encrypt-mapping', action='store_true')
    segmented_parser.add_argument('--encryption-provider', type=str, default=None)
    _add_passphrase_arguments(segmented_parser)

    segment_plan_parser = subparsers.add_parser('plan-segments', help='Preview masking segments derived from policy rules')
    segment_plan_parser.add_argument('source', type=Path)
    segment_plan_parser.add_argument('--policy', type=Path, default=None)
    segment_plan_parser.add_argument('--output', type=Path, default=None)

    scan_parser = subparsers.add_parser('scan', help='Scan a repo for likely sensitive content')
    scan_parser.add_argument('source', type=Path)
    scan_parser.add_argument('--policy', type=Path, default=None)
    scan_parser.add_argument('--output', type=Path, default=None)

    leakage_parser = subparsers.add_parser('leakage-report', help='Estimate semantic leakage that remains after masking')
    leakage_parser.add_argument('source', type=Path)
    leakage_parser.add_argument('--policy', type=Path, default=None)
    leakage_parser.add_argument('--output', type=Path, default=None)
    leakage_parser.add_argument('--fail-on-threshold', action='store_true')

    bundle_parser = subparsers.add_parser('bundle', help='Build a Markdown bundle for external AI tools')
    bundle_parser.add_argument('source', type=Path)
    bundle_parser.add_argument('--policy', type=Path, default=None)
    bundle_parser.add_argument('--output', type=Path, default=Path('ai-bundle.md'))
    bundle_parser.add_argument('--max-files', type=int, default=20)
    bundle_parser.add_argument('--max-chars', type=int, default=12000)
    bundle_parser.add_argument('--leakage-report', type=Path, default=None)
    bundle_parser.add_argument('--fail-on-threshold', action='store_true')

    unmask_parser = subparsers.add_parser('unmask-patch', help='Translate a masked patch')
    unmask_parser.add_argument('patch', type=Path)
    unmask_parser.add_argument('--mapping', type=Path, required=True)
    unmask_parser.add_argument('--output', type=Path, default=Path('translated.patch'))
    _add_passphrase_arguments(unmask_parser)

    apply_parser = subparsers.add_parser('apply', help='Apply a translated patch with git apply')
    apply_parser.add_argument('patch', type=Path)
    apply_parser.add_argument('--target', type=Path, required=True)
    apply_parser.add_argument('--check', action='store_true')
    apply_parser.add_argument('--3way', dest='three_way', action='store_true')

    rekey_parser = subparsers.add_parser(
        'rekey-mapping',
        help='Re-encrypt or decrypt a mapping file without regenerating the masked workspace',
    )
    rekey_parser.add_argument('mapping', type=Path)
    rekey_parser.add_argument('--output', type=Path, default=None)
    rekey_parser.add_argument('--encryption-provider', type=str, default=None)
    _add_passphrase_arguments(rekey_parser)
    _add_new_passphrase_arguments(rekey_parser)

    rekey_runs_parser = subparsers.add_parser(
        'rekey-runs',
        help='Re-wrap mapping files across recent workspace runs',
    )
    rekey_runs_parser.add_argument('workspace', type=Path)
    rekey_runs_parser.add_argument('--limit', type=int, default=None)
    rekey_runs_parser.add_argument('--encryption-provider', type=str, default=None)
    _add_passphrase_arguments(rekey_runs_parser)
    _add_new_passphrase_arguments(rekey_runs_parser)

    subparsers.add_parser('list-providers', help='List available mapping encryption providers')
    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'mask':
            source_root = args.source.resolve()
            output_root = (args.output or source_root.with_name(f'{source_root.name}.masked')).resolve()
            policy = load_policy(args.policy.resolve() if args.policy else None)
            mapping_passphrase = _resolve_passphrase(args, required=args.encrypt_mapping)
            report = mask_workspace(
                source_root,
                output_root,
                policy,
                run_id=args.run_id,
                mapping_passphrase=mapping_passphrase,
                mapping_encryption_provider=args.encryption_provider,
            )
            print(f'masked workspace: {report.output_root}')
            print(f'mapping file: {report.mapping_file}')
            print(f'report file: {report.report_file}')
            return 0

        if args.command == 'mask-segmented':
            source_root = args.source.resolve()
            output_root = (args.output or source_root.with_name(f'{source_root.name}.masked.segmented')).resolve()
            policy = load_policy(args.policy.resolve() if args.policy else None)
            mapping_passphrase = _resolve_passphrase(args, required=args.encrypt_mapping)
            result = mask_segmented_workspace(
                source_root,
                output_root,
                policy,
                run_id_prefix=args.run_id_prefix,
                mapping_passphrase=mapping_passphrase,
                mapping_encryption_provider=args.encryption_provider,
            )
            summary_file = output_root / 'segmented-mask-summary.json'
            summary_file.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')
            print(f'segmented output root: {result.output_root}')
            print(f'segment count: {len(result.segments)}')
            print(f'summary file: {summary_file}')
            return 0

        if args.command == 'plan-segments':
            source_root = args.source.resolve()
            output_root = source_root.with_name(f'{source_root.name}.masked.segmented').resolve()
            policy = load_policy(args.policy.resolve() if args.policy else None)
            segments = plan_mask_segments(source_root, output_root, policy)
            if args.output:
                write_segment_plan(args.output.resolve(), source_root, output_root, segments)
                print(f'segment plan file: {args.output.resolve()}')
            print(f'segment count: {len(segments)}')
            for segment in segments:
                provider = segment.effective_mapping.encryption_provider or 'plaintext'
                mode = 'encrypted' if segment.effective_mapping.require_encryption else 'plain'
                print(f'{segment.segment_id}\t{mode}\t{provider}\t{len(segment.relative_paths)}')
            return 0

        if args.command == 'scan':
            policy = load_policy(args.policy.resolve() if args.policy else None)
            report = scan_workspace(
                args.source.resolve(),
                policy,
                output_file=args.output.resolve() if args.output else None,
            )
            print(f"files scanned: {report['summary']['scanned_files']}")
            print(f"findings: {report['summary']['finding_counts']}")
            if args.output:
                print(f'report file: {args.output.resolve()}')
            return 0

        if args.command == 'leakage-report':
            policy = load_policy(args.policy.resolve() if args.policy else None)
            report, budget = _build_leakage_analysis(
                args.source.resolve(),
                policy,
                output_file=args.output.resolve() if args.output else None,
            )
            _print_leakage_summary(report, budget)
            if args.output:
                print(f'report file: {args.output.resolve()}')
            if args.fail_on_threshold and budget and not budget['passed']:
                print('leakage gate blocked this workspace')
                return LEAKAGE_BUDGET_EXIT_CODE
            return 0

        if args.command == 'bundle':
            source_root = args.source.resolve()
            policy = load_policy(args.policy.resolve() if args.policy else None)
            leakage_output = args.leakage_report.resolve() if args.leakage_report else None
            should_analyze_leakage = args.fail_on_threshold or leakage_output is not None or has_leakage_budget(policy)
            if should_analyze_leakage:
                report, budget = _build_leakage_analysis(source_root, policy, output_file=leakage_output)
                _print_leakage_summary(report, budget)
                if leakage_output:
                    print(f'leakage report file: {leakage_output}')
                if args.fail_on_threshold and budget and not budget['passed']:
                    print('bundle blocked by leakage budget')
                    return LEAKAGE_BUDGET_EXIT_CODE
            bundle = build_markdown_bundle(
                source_root,
                args.output.resolve(),
                max_files=args.max_files,
                max_chars_per_file=args.max_chars,
            )
            print(f'bundle file: {bundle}')
            return 0

        if args.command == 'unmask-patch':
            output_file = translate_patch_file(
                args.patch.resolve(),
                args.mapping.resolve(),
                args.output.resolve(),
                passphrase=_resolve_passphrase(args, required=False),
            )
            print(f'translated patch: {output_file}')
            return 0

        if args.command == 'apply':
            apply_patch_file(
                args.patch.resolve(),
                args.target.resolve(),
                check_only=args.check,
                three_way=args.three_way,
            )
            if args.check:
                print(f'patch check passed: {args.patch.resolve()}')
            else:
                print(f'patch applied: {args.patch.resolve()}')
            return 0

        if args.command == 'rekey-mapping':
            new_passphrase = _resolve_new_passphrase(args)
            output_file = rewrap_mapping_file(
                args.mapping.resolve(),
                output_path=args.output.resolve() if args.output else None,
                passphrase=_resolve_passphrase(args, required=False),
                new_passphrase=new_passphrase,
                encryption_provider=args.encryption_provider,
            )
            mode = 'encrypted' if new_passphrase else 'plaintext'
            print(f'rewrapped mapping: {output_file}')
            print(f'output mode: {mode}')
            return 0

        if args.command == 'rekey-runs':
            new_passphrase = _resolve_new_passphrase(args)
            output_files = rekey_run_mappings(
                args.workspace.resolve(),
                passphrase=_resolve_passphrase(args, required=False),
                new_passphrase=new_passphrase,
                encryption_provider=args.encryption_provider,
                limit=args.limit,
            )
            if not output_files:
                print('rekeyed runs: 0')
                return 0
            mode = 'encrypted' if new_passphrase else 'plaintext'
            print(f'rekeyed runs: {len(output_files)}')
            print(f'output mode: {mode}')
            for path in output_files:
                print(str(path))
            return 0

        if args.command == 'list-providers':
            for provider in describe_mapping_crypto_providers():
                default_marker = ' (default)' if provider['default'] else ''
                print(f"{provider['provider_id']}{default_marker}\t{provider['source']}\t{provider['algorithm']}")
            return 0
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        parser.exit(2, f'error: {exc}\n')
    parser.error('unknown command')
    return 2



def _build_leakage_analysis(
    source_root: Path,
    policy,
    output_file: Path | None,
) -> tuple[dict[str, object], dict[str, object] | None]:
    report = leakage_report(source_root, policy)
    budget = evaluate_leakage_budget(report, policy)
    if budget is not None:
        report['budget'] = budget
    if output_file is not None:
        write_leakage_report(report, output_file)
    return report, budget



def _print_leakage_summary(report: dict[str, object], budget: dict[str, object] | None) -> None:
    print(f"files scanned: {report['summary']['scanned_files']}")
    print(f"total leakage score: {report['summary']['total_score']}")
    print(f"highest risk files: {report['summary']['highest_risk_files']}")
    if budget is None:
        return
    status = 'passed' if budget['passed'] else 'failed'
    print(f'leakage gate: {status}')
    if not budget['passed']:
        for message in budget['messages']:
            print(f'- {message}')



def _add_passphrase_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--passphrase-env', type=str, default=None)
    parser.add_argument('--passphrase-file', type=Path, default=None)



def _add_new_passphrase_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--new-passphrase-env', type=str, default=None)
    parser.add_argument('--new-passphrase-file', type=Path, default=None)



def _resolve_passphrase(args: argparse.Namespace, required: bool) -> str | None:
    return _resolve_passphrase_pair(
        env_name=getattr(args, 'passphrase_env', None),
        file_path=getattr(args, 'passphrase_file', None),
        required=required,
        missing_message='encrypted mapping requires --passphrase-env or --passphrase-file',
        env_option='--passphrase-env',
        file_option='--passphrase-file',
        label='passphrase',
    )



def _resolve_new_passphrase(args: argparse.Namespace) -> str | None:
    return _resolve_passphrase_pair(
        env_name=getattr(args, 'new_passphrase_env', None),
        file_path=getattr(args, 'new_passphrase_file', None),
        required=False,
        missing_message='',
        env_option='--new-passphrase-env',
        file_option='--new-passphrase-file',
        label='new passphrase',
    )



def _resolve_passphrase_pair(
    env_name: str | None,
    file_path: Path | None,
    required: bool,
    missing_message: str,
    env_option: str,
    file_option: str,
    label: str,
) -> str | None:
    if env_name and file_path:
        raise ValueError(f'use either {env_option} or {file_option}, not both')
    if file_path:
        value = file_path.resolve().read_text(encoding='utf-8').strip()
        if not value and required:
            raise ValueError(f'{label} file is empty')
        return value or None
    if env_name:
        value = os.environ.get(env_name, '').strip()
        if not value:
            raise ValueError(f"environment variable '{env_name}' is missing or empty")
        return value
    if required:
        raise ValueError(missing_message)
    return None


if __name__ == '__main__':
    raise SystemExit(main())
