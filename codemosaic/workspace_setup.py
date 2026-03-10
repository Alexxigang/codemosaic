from __future__ import annotations

import os
import re
from pathlib import Path

from codemosaic.crypto import MANAGED_PROVIDER_ID
from codemosaic.key_management import default_key_registry_path, generate_mapping_key, register_key_source
from codemosaic.policy import MappingKeyManagementPolicy, MaskPolicy, load_policy
from codemosaic.presets import init_policy_from_preset


SAFE_SCALAR_RE = re.compile(r'^[A-Za-z0-9_./:-]+$')


def setup_workspace_from_preset(
    workspace_root: Path,
    *,
    preset_name: str = 'balanced-ai-gateway',
    policy_output: Path | None = None,
    key_prefix: str = 'workspace',
    force: bool = False,
    include_signing_key: bool = True,
    key_length: int = 32,
    key_format: str = 'base64',
) -> dict[str, object]:
    workspace_root = workspace_root.resolve()
    policy_output = (policy_output or (workspace_root / 'policy.codemosaic.yaml')).resolve()
    key_registry_path = default_key_registry_path(workspace_root)
    key_dir = workspace_root / '.codemosaic' / 'keys'
    key_dir.mkdir(parents=True, exist_ok=True)

    normalized_prefix = _normalize_key_prefix(key_prefix or workspace_root.name or 'workspace')
    mapping_key_id = f'{normalized_prefix}-mapping'
    signing_key_id = f'{normalized_prefix}-signing'
    mapping_key_file = key_dir / f'{mapping_key_id}.key'
    signing_key_file = key_dir / f'{signing_key_id}.key'

    _ensure_can_write(mapping_key_file, force=force)
    if include_signing_key:
        _ensure_can_write(signing_key_file, force=force)

    preset = init_policy_from_preset(preset_name, policy_output, force=force)

    mapping_key_value = generate_mapping_key(length_bytes=key_length, fmt=key_format)
    mapping_key_file.write_text(mapping_key_value + '\n', encoding='utf-8')
    register_key_source(
        key_registry_path,
        key_id=mapping_key_id,
        source='file',
        reference=f'keys/{mapping_key_file.name}',
        provider=MANAGED_PROVIDER_ID,
        status='active',
        notes='Bootstrapped by setup-workspace',
    )

    if include_signing_key:
        signing_key_value = generate_mapping_key(length_bytes=key_length, fmt=key_format)
        signing_key_file.write_text(signing_key_value + '\n', encoding='utf-8')
        register_key_source(
            key_registry_path,
            key_id=signing_key_id,
            source='file',
            reference=f'keys/{signing_key_file.name}',
            provider=MANAGED_PROVIDER_ID,
            status='active',
            notes='Bootstrapped by setup-workspace',
        )

    policy = load_policy(policy_output)
    registry_file = _relative_path(policy_output.parent, key_registry_path)
    updated_policy = _build_managed_policy(
        policy,
        mapping_key_id=mapping_key_id,
        signing_key_id=signing_key_id if include_signing_key else None,
        registry_file=registry_file,
    )
    policy_output.write_text(render_policy_yaml(updated_policy), encoding='utf-8')

    return {
        'workspace_root': workspace_root,
        'policy_path': policy_output,
        'preset_id': preset.preset_id,
        'registry_path': key_registry_path,
        'mapping_key_id': mapping_key_id,
        'mapping_key_file': mapping_key_file,
        'signing_key_id': signing_key_id if include_signing_key else None,
        'signing_key_file': signing_key_file if include_signing_key else None,
        'include_signing_key': include_signing_key,
    }


def render_policy_yaml(policy: MaskPolicy) -> str:
    lines: list[str] = []

    _emit_section(lines, 'paths', [
        _emit_list('include', policy.paths.include),
        _emit_list('exclude', policy.paths.exclude),
    ])
    _emit_section(lines, 'comments', [_emit_scalar('mode', policy.comments.mode)])
    _emit_section(lines, 'workspace', [_emit_scalar('copy_unmatched', policy.workspace.copy_unmatched)])

    mapping_lines: list[str] = [
        _emit_scalar('require_encryption', policy.mapping.require_encryption),
        _emit_scalar('encryption_provider', policy.mapping.encryption_provider),
    ]
    mapping_lines.extend(_emit_key_management('key_management', policy.mapping.key_management))
    mapping_lines.extend(_emit_key_management('signature_management', policy.mapping.signature_management))
    if policy.mapping.require_signature_for_unmask:
        mapping_lines.append(_emit_scalar('require_signature_for_unmask', policy.mapping.require_signature_for_unmask))
    if policy.mapping.rules:
        mapping_lines.append('  rules:')
        for rule in policy.mapping.rules:
            mapping_lines.append(f'    {rule.pattern}:')
            if rule.require_encryption is not None:
                mapping_lines.append(f'      require_encryption: {_render_scalar(rule.require_encryption)}')
            if rule.encryption_provider is not None:
                mapping_lines.append(f'      encryption_provider: {_render_scalar(rule.encryption_provider)}')
    _emit_section(lines, 'mapping', mapping_lines)

    leakage_lines: list[str] = []
    if policy.leakage.max_total_score is not None:
        leakage_lines.append(_emit_scalar('max_total_score', policy.leakage.max_total_score))
    if policy.leakage.max_file_score is not None:
        leakage_lines.append(_emit_scalar('max_file_score', policy.leakage.max_file_score))
    if policy.leakage.rules:
        leakage_lines.append('  rules:')
        for rule in policy.leakage.rules:
            leakage_lines.append(f'    {rule.pattern}:')
            if rule.max_total_score is not None:
                leakage_lines.append(f'      max_total_score: {_render_scalar(rule.max_total_score)}')
            if rule.max_file_score is not None:
                leakage_lines.append(f'      max_file_score: {_render_scalar(rule.max_file_score)}')
    _emit_section(lines, 'leakage', leakage_lines)

    return '\n'.join(lines) + '\n'


def _build_managed_policy(
    policy: MaskPolicy,
    *,
    mapping_key_id: str,
    signing_key_id: str | None,
    registry_file: str,
) -> MaskPolicy:
    policy.mapping.require_encryption = True
    policy.mapping.encryption_provider = MANAGED_PROVIDER_ID
    policy.mapping.key_management = MappingKeyManagementPolicy(
        key_id=mapping_key_id,
        registry_file=registry_file,
    )
    policy.mapping.signature_management = (
        MappingKeyManagementPolicy(key_id=signing_key_id, registry_file=registry_file)
        if signing_key_id
        else MappingKeyManagementPolicy()
    )
    policy.mapping.require_signature_for_unmask = bool(signing_key_id)
    return policy


def _emit_section(lines: list[str], name: str, content_lines: list[str | None]) -> None:
    filtered = [line for line in content_lines if line]
    if not filtered:
        return
    if lines:
        lines.append('')
    lines.append(f'{name}:')
    lines.extend(filtered)


def _emit_list(name: str, values: list[str]) -> str | None:
    if not values:
        return None
    lines = [f'  {name}:']
    for value in values:
        lines.append(f'    - {_render_scalar(value)}')
    return '\n'.join(lines)


def _emit_scalar(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    return f'  {name}: {_render_scalar(value)}'


def _emit_key_management(name: str, config) -> list[str]:
    if not any((config.source, config.reference, config.key_id, config.registry_file)):
        return []
    lines = [f'  {name}:']
    if config.source is not None:
        lines.append(f'    source: {_render_scalar(config.source)}')
    if config.reference is not None:
        lines.append(f'    reference: {_render_scalar(config.reference)}')
    if config.key_id is not None:
        lines.append(f'    key_id: {_render_scalar(config.key_id)}')
    if config.registry_file is not None:
        lines.append(f'    registry_file: {_render_scalar(config.registry_file)}')
    return lines


def _render_scalar(value: object) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if SAFE_SCALAR_RE.match(text):
        return text
    escaped = text.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def _relative_path(base_dir: Path, target_path: Path) -> str:
    relative = os.path.relpath(target_path.resolve(), start=base_dir.resolve())
    return relative.replace('\\', '/')


def _normalize_key_prefix(value: str) -> str:
    normalized = re.sub(r'[^a-z0-9]+', '-', value.strip().lower()).strip('-')
    return normalized or 'workspace'


def _ensure_can_write(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise ValueError(f'output already exists: {path.resolve()}')
