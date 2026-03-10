from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from codemosaic.mapping import rewrap_mapping_file, verify_mapping_file


@dataclass(frozen=True, slots=True)
class RunMappingInfo:
    run_id: str
    run_directory: Path
    mapping_file: Path
    encrypted: bool
    sort_time: float


@dataclass(frozen=True, slots=True)
class RunAuditRecord:
    run_id: str
    run_directory: Path
    mapping_file: Path
    encrypted: bool
    signed: bool
    verification_status: str
    sort_time: float
    generated_at: str | None = None
    encryption_provider: str | None = None
    mapping_key_id: str | None = None
    signature_key_id: str | None = None
    source_root: str | None = None
    output_root: str | None = None
    file_count: int | None = None
    verification_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'run_id': self.run_id,
            'run_directory': str(self.run_directory),
            'mapping_file': str(self.mapping_file),
            'encrypted': self.encrypted,
            'signed': self.signed,
            'verification_status': self.verification_status,
        }
        if self.generated_at:
            payload['generated_at'] = self.generated_at
        if self.encryption_provider:
            payload['encryption_provider'] = self.encryption_provider
        if self.mapping_key_id:
            payload['mapping_key_id'] = self.mapping_key_id
        if self.signature_key_id:
            payload['signature_key_id'] = self.signature_key_id
        if self.source_root:
            payload['source_root'] = self.source_root
        if self.output_root:
            payload['output_root'] = self.output_root
        if self.file_count is not None:
            payload['file_count'] = self.file_count
        if self.verification_error:
            payload['verification_error'] = self.verification_error
        return payload



def list_run_mappings(workspace_root: Path) -> list[RunMappingInfo]:
    runs_root = workspace_root / '.codemosaic' / 'runs'
    if not runs_root.exists():
        return []
    items: list[RunMappingInfo] = []
    for entry in runs_root.iterdir():
        if not entry.is_dir():
            continue
        mapping_file = _find_mapping_file(entry)
        if mapping_file is None:
            continue
        items.append(
            RunMappingInfo(
                run_id=entry.name,
                run_directory=entry,
                mapping_file=mapping_file,
                encrypted=mapping_file.name.endswith('.enc.json'),
                sort_time=_safe_mtime(entry / 'report.json') or _safe_mtime(mapping_file) or _safe_mtime(entry),
            )
        )
    return sorted(items, key=lambda item: item.sort_time, reverse=True)



def audit_run_mappings(
    workspace_root: Path,
    *,
    signing_key: str | None = None,
    require_signature: bool = False,
    limit: int | None = None,
) -> list[RunAuditRecord]:
    mappings = list_run_mappings(workspace_root)
    if limit is not None:
        mappings = mappings[:limit]
    records: list[RunAuditRecord] = []
    failures: list[str] = []
    for mapping in mappings:
        record = _audit_single_mapping(mapping, signing_key=signing_key)
        records.append(record)
        if require_signature and record.verification_status != 'verified':
            failures.append(f"{record.run_id}: {record.verification_status}")
    if require_signature and failures:
        raise ValueError('run audit failed signature policy: ' + '; '.join(failures))
    return records



def rekey_run_mappings(
    workspace_root: Path,
    passphrase: str | None = None,
    new_passphrase: str | None = None,
    encryption_provider: str | None = None,
    limit: int | None = None,
    metadata_overrides: dict[str, object] | None = None,
    signing_key: str | None = None,
    signing_metadata: dict[str, object] | None = None,
) -> list[Path]:
    mappings = list_run_mappings(workspace_root)
    if limit is not None:
        mappings = mappings[:limit]
    if not mappings:
        return []
    outputs: list[Path] = []
    for mapping in mappings:
        outputs.append(
            rewrap_mapping_file(
                mapping.mapping_file,
                passphrase=passphrase if mapping.encrypted else None,
                new_passphrase=new_passphrase,
                encryption_provider=encryption_provider if new_passphrase else None,
                metadata_overrides=metadata_overrides,
                signing_key=signing_key,
                signing_metadata=signing_metadata,
            )
        )
    return outputs



def _audit_single_mapping(mapping: RunMappingInfo, *, signing_key: str | None) -> RunAuditRecord:
    raw_payload = json.loads(mapping.mapping_file.read_text(encoding='utf-8'))
    report_payload = _load_report_payload(mapping.run_directory / 'report.json')
    metadata = _extract_metadata(raw_payload)
    header = raw_payload.get('header', {}) if isinstance(raw_payload, dict) else {}
    if not isinstance(header, dict):
        header = {}
    integrity = raw_payload.get('integrity', {}) if isinstance(raw_payload, dict) else {}
    if not isinstance(integrity, dict):
        integrity = {}
    signed = bool(integrity)
    verification_status = 'unsigned'
    verification_error = None
    if signed and signing_key:
        try:
            verify_mapping_file(mapping.mapping_file, signing_key=signing_key, require_signature=True)
            verification_status = 'verified'
        except ValueError as exc:
            verification_status = 'failed'
            verification_error = str(exc)
    elif signed:
        verification_status = 'signed-unchecked'
    return RunAuditRecord(
        run_id=mapping.run_id,
        run_directory=mapping.run_directory,
        mapping_file=mapping.mapping_file,
        encrypted=mapping.encrypted,
        signed=signed,
        verification_status=verification_status,
        sort_time=mapping.sort_time,
        generated_at=_pick_str(metadata, 'generated_at') or _pick_str(header, 'generated_at'),
        encryption_provider=(
            _pick_str(metadata, 'encryption_provider')
            or _pick_str(header, 'encryption_provider')
            or _pick_str(raw_payload, 'provider')
        ),
        mapping_key_id=_extract_key_id(metadata, header, 'key_management'),
        signature_key_id=_extract_signature_key_id(integrity, metadata, header),
        source_root=_pick_str(report_payload, 'source_root') or _pick_str(metadata, 'source_root'),
        output_root=_pick_str(report_payload, 'output_root') or _pick_str(metadata, 'output_root'),
        file_count=_count_report_files(report_payload),
        verification_error=verification_error,
    )



def _extract_metadata(raw_payload: object) -> dict[str, object]:
    if not isinstance(raw_payload, dict):
        return {}
    if 'metadata' in raw_payload and isinstance(raw_payload.get('metadata'), dict):
        return dict(raw_payload['metadata'])
    header = raw_payload.get('header', {})
    if isinstance(header, dict):
        return dict(header)
    return {}



def _extract_key_id(metadata: dict[str, object], header: dict[str, object], field_name: str) -> str | None:
    for container in (metadata, header):
        value = container.get(field_name, {}) if isinstance(container, dict) else {}
        if isinstance(value, dict) and value.get('key_id') not in (None, ''):
            return str(value['key_id'])
    return None



def _extract_signature_key_id(integrity: dict[str, object], metadata: dict[str, object], header: dict[str, object]) -> str | None:
    key_management = integrity.get('key_management', {})
    if isinstance(key_management, dict) and key_management.get('key_id') not in (None, ''):
        return str(key_management['key_id'])
    return _extract_key_id(metadata, header, 'signature_management')



def _load_report_payload(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else {}



def _count_report_files(report_payload: dict[str, object]) -> int | None:
    files = report_payload.get('files', [])
    if isinstance(files, list):
        return len(files)
    return None



def _pick_str(payload: dict[str, object], key: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if value in (None, ''):
        return None
    return str(value)



def _find_mapping_file(run_directory: Path) -> Path | None:
    encrypted = run_directory / 'mapping.enc.json'
    if encrypted.exists():
        return encrypted
    plain = run_directory / 'mapping.json'
    if plain.exists():
        return plain
    return None



def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0
