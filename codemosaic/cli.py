from __future__ import annotations

import argparse
import json
from pathlib import Path

from codemosaic.bundles import build_markdown_bundle
from codemosaic.crypto import describe_mapping_crypto_providers
from codemosaic.key_management import (
    KeyManagementConfig,
    default_key_registry_path,
    generate_mapping_key,
    load_key_registry,
    register_key_source,
    resolve_key_material,
)
from codemosaic.leakage import evaluate_leakage_budget, has_leakage_budget, leakage_report, write_leakage_report
from codemosaic.mapping import rewrap_mapping_file
from codemosaic.patching import apply_patch_file, translate_patch_file
from codemosaic.policy import MaskPolicy, load_policy
from codemosaic.runs import rekey_run_mappings
from codemosaic.scanning import scan_workspace
from codemosaic.segmentation import mask_segmented_workspace, plan_mask_segments, write_segment_plan
from codemosaic.workspace import mask_workspace, resolve_workspace_mapping_policy


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
    _add_key_material_arguments(mask_parser)

    segmented_parser = subparsers.add_parser('mask-segmented', help='Generate multiple masked workspaces grouped by policy segments')
    segmented_parser.add_argument('source', type=Path)
    segmented_parser.add_argument('--policy', type=Path, default=None)
    segmented_parser.add_argument('--output', type=Path, default=None)
    segmented_parser.add_argument('--run-id-prefix', type=str, default=None)
    segmented_parser.add_argument('--encrypt-mapping', action='store_true')
    segmented_parser.add_argument('--encryption-provider', type=str, default=None)
    _add_key_material_arguments(segmented_parser)

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
    _add_key_material_arguments(unmask_parser)

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
    _add_key_material_arguments(rekey_parser)
    _add_new_key_material_arguments(rekey_parser)

    rekey_runs_parser = subparsers.add_parser(
        'rekey-runs',
        help='Re-wrap mapping files across recent workspace runs',
    )
    rekey_runs_parser.add_argument('workspace', type=Path)
    rekey_runs_parser.add_argument('--limit', type=int, default=None)
    rekey_runs_parser.add_argument('--encryption-provider', type=str, default=None)
    _add_key_material_arguments(rekey_runs_parser)
    _add_new_key_material_arguments(rekey_runs_parser)

    generate_key_parser = subparsers.add_parser('generate-key', help='Generate high-entropy mapping key material')
    generate_key_parser.add_argument('--output', type=Path, default=None)
    generate_key_parser.add_argument('--format', choices=['base64', 'hex'], default='base64')
    generate_key_parser.add_argument('--length', type=int, default=32)
    generate_key_parser.add_argument('--force', action='store_true')

    register_key_parser = subparsers.add_parser('register-key-source', help='Register a reusable key source for a workspace')
    register_key_parser.add_argument('workspace', type=Path)
    register_key_parser.add_argument('--key-id', type=str, required=True)
    register_key_parser.add_argument('--source', type=str, choices=['env', 'file'], required=True)
    register_key_parser.add_argument('--reference', type=str, required=True)
    register_key_parser.add_argument('--provider', type=str, default='managed-v1')
    register_key_parser.add_argument('--status', type=str, default='active')
    register_key_parser.add_argument('--notes', type=str, default=None)
    register_key_parser.add_argument('--key-registry', type=Path, default=None)

    list_keys_parser = subparsers.add_parser('list-key-sources', help='List key sources registered for a workspace')
    list_keys_parser.add_argument('workspace', type=Path)
    list_keys_parser.add_argument('--key-registry', type=Path, default=None)

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
            encryption_requested = args.encrypt_mapping or _has_key_material_inputs(args)
            effective_mapping = resolve_workspace_mapping_policy(
                source_root,
                output_root,
                policy,
                encryption_requested=encryption_requested,
                provider_override=args.encryption_provider,
            )
            registry_path = _resolve_registry_path(args, workspace_root=source_root, policy=policy)
            key_material = _resolve_active_key_material(
                args,
                policy,
                registry_path=registry_path,
                required=effective_mapping.require_encryption or encryption_requested,
                missing_message=(
                    'policy requires encrypted mapping; provide --key-env/--key-file, --passphrase-env/--passphrase-file, or register a key source in the key registry'
                    if effective_mapping.require_encryption and not encryption_requested
                    else 'encrypted mapping requires --key-env/--key-file, --passphrase-env/--passphrase-file, or a matching key registry entry'
                ),
            )
            report = mask_workspace(
                source_root,
                output_root,
                policy,
                run_id=args.run_id,
                mapping_passphrase=key_material.secret,
                mapping_encryption_provider=args.encryption_provider,
                mapping_key_metadata=key_material.to_metadata() if key_material.secret else None,
            )
            print(f'masked workspace: {report.output_root}')
            print(f'mapping file: {report.mapping_file}')
            print(f"report file: {source_root / '.codemosaic' / 'runs' / report.run_id / 'report.json'}")
            return 0

        if args.command == 'mask-segmented':
            source_root = args.source.resolve()
            output_root = (args.output or source_root.with_name(f'{source_root.name}.masked.segmented')).resolve()
            policy = load_policy(args.policy.resolve() if args.policy else None)
            encryption_requested = args.encrypt_mapping or _has_key_material_inputs(args)
            effective_mapping = resolve_workspace_mapping_policy(
                source_root,
                output_root,
                policy,
                encryption_requested=encryption_requested,
                provider_override=args.encryption_provider,
            )
            registry_path = _resolve_registry_path(args, workspace_root=source_root, policy=policy)
            key_material = _resolve_active_key_material(
                args,
                policy,
                registry_path=registry_path,
                required=effective_mapping.require_encryption or encryption_requested,
                missing_message=(
                    'policy requires encrypted mapping; provide --key-env/--key-file, --passphrase-env/--passphrase-file, or register a key source in the key registry'
                    if effective_mapping.require_encryption and not encryption_requested
                    else 'encrypted mapping requires --key-env/--key-file, --passphrase-env/--passphrase-file, or a matching key registry entry'
                ),
            )
            result = mask_segmented_workspace(
                source_root,
                output_root,
                policy,
                run_id_prefix=args.run_id_prefix,
                mapping_passphrase=key_material.secret,
                mapping_encryption_provider=args.encryption_provider,
                mapping_key_metadata=key_material.to_metadata() if key_material.secret else None,
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
            mapping_file = args.mapping.resolve()
            registry_path = _resolve_registry_path(
                args,
                workspace_root=_infer_workspace_root_from_mapping(mapping_file),
                policy=None,
            )
            key_material = _resolve_active_key_material(args, None, registry_path=registry_path, required=False)
            output_file = translate_patch_file(
                args.patch.resolve(),
                mapping_file,
                args.output.resolve(),
                passphrase=key_material.secret,
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
            mapping_file = args.mapping.resolve()
            workspace_root = _infer_workspace_root_from_mapping(mapping_file)
            registry_path = _resolve_registry_path(args, workspace_root=workspace_root, policy=None)
            new_registry_path = _resolve_registry_path(args, workspace_root=workspace_root, policy=None, registry_attr='new_key_registry') or registry_path
            current_key = _resolve_active_key_material(args, None, registry_path=registry_path, required=False)
            new_key = _resolve_new_key_material(args, registry_path=new_registry_path)
            output_file = rewrap_mapping_file(
                mapping_file,
                output_path=args.output.resolve() if args.output else None,
                passphrase=current_key.secret,
                new_passphrase=new_key.secret,
                encryption_provider=args.encryption_provider,
                metadata_overrides=_build_rekey_metadata(new_key, args.encryption_provider),
            )
            mode = 'encrypted' if new_key.secret else 'plaintext'
            print(f'rewrapped mapping: {output_file}')
            print(f'output mode: {mode}')
            return 0

        if args.command == 'rekey-runs':
            workspace_root = args.workspace.resolve()
            registry_path = _resolve_registry_path(args, workspace_root=workspace_root, policy=None)
            new_registry_path = _resolve_registry_path(args, workspace_root=workspace_root, policy=None, registry_attr='new_key_registry') or registry_path
            current_key = _resolve_active_key_material(args, None, registry_path=registry_path, required=False)
            new_key = _resolve_new_key_material(args, registry_path=new_registry_path)
            output_files = rekey_run_mappings(
                workspace_root,
                passphrase=current_key.secret,
                new_passphrase=new_key.secret,
                encryption_provider=args.encryption_provider,
                limit=args.limit,
                metadata_overrides=_build_rekey_metadata(new_key, args.encryption_provider),
            )
            if not output_files:
                print('rekeyed runs: 0')
                return 0
            mode = 'encrypted' if new_key.secret else 'plaintext'
            print(f'rekeyed runs: {len(output_files)}')
            print(f'output mode: {mode}')
            for path in output_files:
                print(str(path))
            return 0

        if args.command == 'generate-key':
            key_value = generate_mapping_key(length_bytes=args.length, fmt=args.format)
            if args.output:
                output_path = args.output.resolve()
                if output_path.exists() and not args.force:
                    raise ValueError(f'output already exists: {output_path}')
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(key_value + '\n', encoding='utf-8')
                print(f'mapping key file: {output_path}')
            else:
                print(key_value)
            return 0

        if args.command == 'register-key-source':
            workspace_root = args.workspace.resolve()
            registry_path = _resolve_registry_path(args, workspace_root=workspace_root, policy=None)
            if registry_path is None:
                registry_path = default_key_registry_path(workspace_root)
            entry = register_key_source(
                registry_path,
                key_id=args.key_id,
                source=args.source,
                reference=args.reference,
                provider=args.provider,
                status=args.status,
                notes=args.notes,
            )
            print(f'key registry: {registry_path}')
            print(f'registered key: {entry.key_id}')
            print(f'source: {entry.source}')
            print(f'reference: {entry.reference}')
            return 0

        if args.command == 'list-key-sources':
            workspace_root = args.workspace.resolve()
            registry_path = _resolve_registry_path(args, workspace_root=workspace_root, policy=None)
            if registry_path is None:
                registry_path = default_key_registry_path(workspace_root)
            entries = load_key_registry(registry_path)
            print(f'key registry: {registry_path}')
            print(f'registered keys: {len(entries)}')
            for entry in entries:
                print(f'{entry.key_id}\t{entry.source}\t{entry.reference}\t{entry.provider}\t{entry.status}')
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



def _add_key_material_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--key-env', type=str, default=None, help='Preferred: environment variable containing mapping key material')
    parser.add_argument('--key-file', type=Path, default=None, help='Preferred: file containing mapping key material')
    parser.add_argument('--key-id', type=str, default=None, help='Logical key identifier for direct or registry-backed resolution')
    parser.add_argument('--key-registry', type=Path, default=None, help='Optional key registry file')
    parser.add_argument('--passphrase-env', type=str, default=None, help='Legacy alias for environment-backed mapping secret')
    parser.add_argument('--passphrase-file', type=Path, default=None, help='Legacy alias for file-backed mapping secret')



def _add_new_key_material_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--new-key-env', type=str, default=None, help='Environment variable containing replacement mapping key material')
    parser.add_argument('--new-key-file', type=Path, default=None, help='File containing replacement mapping key material')
    parser.add_argument('--new-key-id', type=str, default=None, help='Logical key identifier for the rewrapped mapping')
    parser.add_argument('--new-key-registry', type=Path, default=None, help='Optional key registry file for replacement key lookup')
    parser.add_argument('--new-passphrase-env', type=str, default=None, help='Legacy alias for replacement mapping secret')
    parser.add_argument('--new-passphrase-file', type=Path, default=None, help='Legacy alias for replacement mapping secret file')



def _resolve_active_key_material(
    args: argparse.Namespace,
    policy: MaskPolicy | None,
    *,
    registry_path: Path | None,
    required: bool,
    missing_message: str = 'encrypted mapping requires --key-env/--key-file, --passphrase-env/--passphrase-file, or a matching key registry entry',
):
    return resolve_key_material(
        key_env=getattr(args, 'key_env', None),
        key_file=getattr(args, 'key_file', None),
        key_id=getattr(args, 'key_id', None),
        passphrase_env=getattr(args, 'passphrase_env', None),
        passphrase_file=getattr(args, 'passphrase_file', None),
        policy=_policy_key_management(policy),
        policy_base_dir=_policy_base_dir(policy),
        registry_path=registry_path,
        required=required,
        missing_message=missing_message,
    )



def _resolve_new_key_material(args: argparse.Namespace, *, registry_path: Path | None):
    return resolve_key_material(
        key_env=getattr(args, 'new_key_env', None),
        key_file=getattr(args, 'new_key_file', None),
        key_id=getattr(args, 'new_key_id', None),
        passphrase_env=getattr(args, 'new_passphrase_env', None),
        passphrase_file=getattr(args, 'new_passphrase_file', None),
        policy=None,
        registry_path=registry_path,
        required=False,
        missing_message='',
        key_env_option='--new-key-env',
        key_file_option='--new-key-file',
        passphrase_env_option='--new-passphrase-env',
        passphrase_file_option='--new-passphrase-file',
    )



def _resolve_registry_path(
    args: argparse.Namespace,
    *,
    workspace_root: Path | None,
    policy: MaskPolicy | None,
    registry_attr: str = 'key_registry',
) -> Path | None:
    explicit = getattr(args, registry_attr, None)
    if explicit is not None:
        return explicit.resolve()
    if registry_attr == 'key_registry' and policy is not None:
        mapping_key = policy.mapping.key_management
        if mapping_key.registry_file:
            base_dir = _policy_base_dir(policy)
            registry_file = Path(mapping_key.registry_file)
            if not registry_file.is_absolute() and base_dir is not None:
                return (base_dir / registry_file).resolve()
            return registry_file.resolve()
    if workspace_root is not None:
        return default_key_registry_path(workspace_root.resolve())
    return None



def _has_key_material_inputs(args: argparse.Namespace) -> bool:
    return any(
        getattr(args, name, None)
        for name in ('key_env', 'key_file', 'key_id', 'passphrase_env', 'passphrase_file')
    )



def _policy_key_management(policy: MaskPolicy | None) -> KeyManagementConfig | None:
    if policy is None:
        return None
    mapping_key = policy.mapping.key_management
    if not (mapping_key.source or mapping_key.key_id):
        return None
    return KeyManagementConfig(
        source=mapping_key.source,
        reference=mapping_key.reference,
        key_id=mapping_key.key_id,
        registry_file=mapping_key.registry_file,
    )



def _policy_base_dir(policy: MaskPolicy | None) -> Path | None:
    if policy is None or not policy.source_path:
        return None
    return Path(policy.source_path).resolve().parent



def _infer_workspace_root_from_mapping(mapping_file: Path) -> Path | None:
    candidate = mapping_file.resolve()
    if candidate.parent.parent.name == 'runs' and candidate.parent.parent.parent.name == '.codemosaic':
        return candidate.parent.parent.parent.parent
    return None



def _build_rekey_metadata(key_material, encryption_provider: str | None) -> dict[str, object]:
    if key_material.secret:
        return {
            'key_management': key_material.to_metadata(),
            'encryption_provider': encryption_provider,
        }
    return {
        'key_management': {'enabled': False},
        'encryption_provider': None,
    }


if __name__ == '__main__':
    raise SystemExit(main())
