from __future__ import annotations

import base64
import os
import secrets
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_KEY_SOURCES = {'env', 'file'}


@dataclass(frozen=True, slots=True)
class KeyManagementConfig:
    source: str | None = None
    reference: str | None = None
    key_id: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedKeyMaterial:
    secret: str | None
    source: str | None = None
    reference: str | None = None
    key_id: str | None = None
    origin: str | None = None

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



def resolve_key_material(
    *,
    key_env: str | None = None,
    key_file: Path | None = None,
    key_id: str | None = None,
    passphrase_env: str | None = None,
    passphrase_file: Path | None = None,
    policy: KeyManagementConfig | None = None,
    policy_base_dir: Path | None = None,
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
        )
    if cli_passphrase_value:
        return ResolvedKeyMaterial(
            secret=cli_passphrase_value,
            source=cli_passphrase_source,
            reference=cli_passphrase_reference,
            key_id=key_id,
            origin='cli-passphrase',
        )
    if policy and policy.source:
        value = _read_source(policy.source, policy.reference, base_dir=policy_base_dir)
        return ResolvedKeyMaterial(
            secret=value,
            source=policy.source,
            reference=policy.reference,
            key_id=key_id or policy.key_id,
            origin='policy',
        )
    if required:
        raise ValueError(missing_message)
    return ResolvedKeyMaterial(secret=None, key_id=key_id or (policy.key_id if policy else None))



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
