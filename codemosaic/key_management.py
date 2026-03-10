from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from codemosaic.crypto import MANAGED_PROVIDER_ID


SUPPORTED_KEY_SOURCES = {'env', 'file'}
SUPPORTED_KEY_STATUSES = {'active', 'decrypt-only', 'retired'}


@dataclass(frozen=True, slots=True)
class KeyManagementConfig:
    source: str | None = None
    reference: str | None = None
    key_id: str | None = None
    registry_file: str | None = None


@dataclass(frozen=True, slots=True)
class RegisteredKeySource:
    key_id: str
    source: str
    reference: str
    provider: str = MANAGED_PROVIDER_ID
    status: str = 'active'
    created_at: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'key_id': self.key_id,
            'source': self.source,
            'reference': self.reference,
            'provider': self.provider,
            'status': self.status,
        }
        if self.created_at:
            payload['created_at'] = self.created_at
        if self.notes:
            payload['notes'] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class ResolvedKeyMaterial:
    secret: str | None
    source: str | None = None
    reference: str | None = None
    key_id: str | None = None
    origin: str | None = None
    registry_path: str | None = None

    def to_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            'enabled': bool(self.secret),
        }
        if self.source:
            metadata['source'] = self.source
        if self.reference:
            metadata['reference'] = self.reference
        if self.key_id:
            metadata['key_id'] = self.key_id
        if self.origin:
            metadata['origin'] = self.origin
        if self.registry_path:
            metadata['registry_path'] = self.registry_path
        return metadata



def generate_mapping_key(length_bytes: int = 32, fmt: str = 'base64') -> str:
    if length_bytes < 16:
        raise ValueError('mapping key length must be at least 16 bytes')
    material = secrets.token_bytes(length_bytes)
    if fmt == 'base64':
        return 'base64:' + base64.urlsafe_b64encode(material).decode('ascii').rstrip('=')
    if fmt == 'hex':
        return 'hex:' + material.hex()
    raise ValueError(f"unsupported key format: '{fmt}'")



def default_key_registry_path(workspace_root: Path) -> Path:
    return workspace_root / '.codemosaic' / 'key-registry.json'



def load_key_registry(path: Path) -> list[RegisteredKeySource]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding='utf-8'))
    items = payload.get('keys', []) if isinstance(payload, dict) else []
    entries: list[RegisteredKeySource] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key_id = str(item.get('key_id', '')).strip()
        source = str(item.get('source', '')).strip()
        reference = str(item.get('reference', '')).strip()
        if not key_id or not source or not reference:
            continue
        entries.append(
            RegisteredKeySource(
                key_id=key_id,
                source=source,
                reference=reference,
                provider=str(item.get('provider', MANAGED_PROVIDER_ID) or MANAGED_PROVIDER_ID),
                status=_normalize_status(item.get('status', 'active')),
                created_at=str(item.get('created_at')) if item.get('created_at') is not None else None,
                notes=str(item.get('notes')) if item.get('notes') is not None else None,
            )
        )
    return entries



def find_registered_key_source(
    path: Path,
    key_id: str,
    *,
    allowed_statuses: set[str] | None = None,
) -> RegisteredKeySource | None:
    normalized = key_id.strip()
    for entry in load_key_registry(path):
        if entry.key_id != normalized:
            continue
        if allowed_statuses is not None and entry.status not in allowed_statuses:
            return None
        return entry
    return None



def register_key_source(
    path: Path,
    *,
    key_id: str,
    source: str,
    reference: str,
    provider: str = MANAGED_PROVIDER_ID,
    status: str = 'active',
    notes: str | None = None,
) -> RegisteredKeySource:
    normalized_source = source.strip()
    if normalized_source not in SUPPORTED_KEY_SOURCES:
        raise ValueError(f"unsupported key management source: '{normalized_source}'")
    normalized_status = _normalize_status(status)
    timestamp = datetime.now().isoformat(timespec='seconds')
    entry = RegisteredKeySource(
        key_id=key_id.strip(),
        source=normalized_source,
        reference=reference.strip(),
        provider=provider.strip() or MANAGED_PROVIDER_ID,
        status=normalized_status,
        created_at=timestamp,
        notes=notes.strip() if isinstance(notes, str) and notes.strip() else None,
    )
    existing = load_key_registry(path)
    updated: list[RegisteredKeySource] = []
    replaced = False
    for current in existing:
        if current.key_id == entry.key_id:
            updated.append(
                RegisteredKeySource(
                    key_id=entry.key_id,
                    source=entry.source,
                    reference=entry.reference,
                    provider=entry.provider,
                    status=entry.status,
                    created_at=current.created_at or entry.created_at,
                    notes=entry.notes,
                )
            )
            replaced = True
        else:
            updated.append(current)
    if not replaced:
        updated.append(entry)
    write_key_registry(path, updated)
    return find_registered_key_source(path, entry.key_id) or entry



def update_key_source_status(path: Path, *, key_id: str, status: str) -> RegisteredKeySource:
    normalized_key_id = key_id.strip()
    normalized_status = _normalize_status(status)
    existing = load_key_registry(path)
    if not existing:
        raise ValueError(f'key registry is empty: {path}')
    updated: list[RegisteredKeySource] = []
    selected: RegisteredKeySource | None = None
    for current in existing:
        if current.key_id == normalized_key_id:
            selected = RegisteredKeySource(
                key_id=current.key_id,
                source=current.source,
                reference=current.reference,
                provider=current.provider,
                status=normalized_status,
                created_at=current.created_at,
                notes=current.notes,
            )
            updated.append(selected)
        else:
            updated.append(current)
    if selected is None:
        raise ValueError(f"key id not found in registry: '{normalized_key_id}'")
    write_key_registry(path, updated)
    return selected



def write_key_registry(path: Path, entries: list[RegisteredKeySource]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'format': 'codemosaic-key-registry-v1',
        'keys': [entry.to_dict() for entry in sorted(entries, key=lambda item: item.key_id)],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return path



def resolve_key_material(
    *,
    key_env: str | None = None,
    key_file: Path | None = None,
    key_id: str | None = None,
    passphrase_env: str | None = None,
    passphrase_file: Path | None = None,
    policy: KeyManagementConfig | None = None,
    policy_base_dir: Path | None = None,
    registry_path: Path | None = None,
    usage_mode: str = 'encrypt',
    required: bool = False,
    missing_message: str,
    key_env_option: str = '--key-env',
    key_file_option: str = '--key-file',
    passphrase_env_option: str = '--passphrase-env',
    passphrase_file_option: str = '--passphrase-file',
) -> ResolvedKeyMaterial:
    cli_key_value, cli_key_source, cli_key_reference = _resolve_cli_source(
        env_name=key_env,
        file_path=key_file,
        env_option=key_env_option,
        file_option=key_file_option,
        label='mapping key',
    )
    cli_passphrase_value, cli_passphrase_source, cli_passphrase_reference = _resolve_cli_source(
        env_name=passphrase_env,
        file_path=passphrase_file,
        env_option=passphrase_env_option,
        file_option=passphrase_file_option,
        label='mapping passphrase',
    )
    if cli_key_value and cli_passphrase_value:
        raise ValueError(f'use either {key_env_option}/{key_file_option} or {passphrase_env_option}/{passphrase_file_option}, not both')
    if cli_key_value:
        return ResolvedKeyMaterial(
            secret=cli_key_value,
            source=cli_key_source,
            reference=cli_key_reference,
            key_id=key_id,
            origin='cli-key',
            registry_path=str(registry_path) if registry_path else None,
        )
    if cli_passphrase_value:
        return ResolvedKeyMaterial(
            secret=cli_passphrase_value,
            source=cli_passphrase_source,
            reference=cli_passphrase_reference,
            key_id=key_id,
            origin='cli-passphrase',
            registry_path=str(registry_path) if registry_path else None,
        )
    effective_key_id = key_id or (policy.key_id if policy else None)
    if policy and policy.source:
        value = _read_source(policy.source, policy.reference, base_dir=policy_base_dir)
        return ResolvedKeyMaterial(
            secret=value,
            source=policy.source,
            reference=policy.reference,
            key_id=effective_key_id,
            origin='policy',
            registry_path=str(registry_path) if registry_path else None,
        )
    if effective_key_id and registry_path is not None:
        raw_entry = find_registered_key_source(registry_path, effective_key_id)
        if raw_entry is not None and not _status_allows_usage(raw_entry.status, usage_mode):
            raise ValueError(_status_block_message(raw_entry.key_id, raw_entry.status, usage_mode))
        entry = find_registered_key_source(registry_path, effective_key_id, allowed_statuses=_allowed_statuses_for_usage(usage_mode))
        if entry is not None:
            value = _read_source(entry.source, entry.reference, base_dir=registry_path.parent)
            return ResolvedKeyMaterial(
                secret=value,
                source=entry.source,
                reference=entry.reference,
                key_id=entry.key_id,
                origin='registry',
                registry_path=str(registry_path),
            )
    if required:
        raise ValueError(missing_message)
    return ResolvedKeyMaterial(
        secret=None,
        key_id=effective_key_id,
        registry_path=str(registry_path) if registry_path else None,
    )



def _resolve_cli_source(
    *,
    env_name: str | None,
    file_path: Path | None,
    env_option: str,
    file_option: str,
    label: str,
) -> tuple[str | None, str | None, str | None]:
    if env_name and file_path:
        raise ValueError(f'use either {env_option} or {file_option}, not both')
    if file_path:
        value = file_path.resolve().read_text(encoding='utf-8').strip()
        if not value:
            raise ValueError(f'{label} file is empty')
        return value, 'file', str(file_path)
    if env_name:
        value = os.environ.get(env_name, '').strip()
        if not value:
            raise ValueError(f"environment variable '{env_name}' is missing or empty")
        return value, 'env', env_name
    return None, None, None



def _read_source(source: str | None, reference: str | None, base_dir: Path | None = None) -> str:
    if not source:
        raise ValueError('missing key management source')
    if source not in SUPPORTED_KEY_SOURCES:
        raise ValueError(f"unsupported key management source: '{source}'")
    if not reference:
        raise ValueError('key management reference is required')
    if source == 'env':
        value = os.environ.get(reference, '').strip()
        if not value:
            raise ValueError(f"environment variable '{reference}' is missing or empty")
        return value
    key_file = Path(reference)
    if not key_file.is_absolute() and base_dir is not None:
        key_file = (base_dir / key_file).resolve()
    else:
        key_file = key_file.resolve()
    value = key_file.read_text(encoding='utf-8').strip()
    if not value:
        raise ValueError(f'key file is empty: {key_file}')
    return value



def _normalize_status(value: object) -> str:
    normalized = str(value or 'active').strip().lower()
    if normalized not in SUPPORTED_KEY_STATUSES:
        raise ValueError(f"unsupported key status: '{normalized}'")
    return normalized



def _allowed_statuses_for_usage(usage_mode: str) -> set[str]:
    if usage_mode == 'decrypt':
        return {'active', 'decrypt-only'}
    if usage_mode == 'encrypt':
        return {'active'}
    raise ValueError(f"unsupported key usage mode: '{usage_mode}'")



def _status_allows_usage(status: str, usage_mode: str) -> bool:
    return status in _allowed_statuses_for_usage(usage_mode)



def _status_block_message(key_id: str, status: str, usage_mode: str) -> str:
    if usage_mode == 'encrypt':
        return f"key '{key_id}' is marked '{status}' and cannot be used for new encryption operations"
    return f"key '{key_id}' is marked '{status}' and cannot be used for decrypt operations"
