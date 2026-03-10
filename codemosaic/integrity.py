from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass


INTEGRITY_FORMAT = 'codemosaic-integrity-v1'
INTEGRITY_ALGORITHM = 'hmac-sha256'
SAFE_INTEGRITY_KEY_FIELDS = {'source', 'reference', 'key_id', 'origin', 'registry_path'}


@dataclass(frozen=True, slots=True)
class MappingIntegrityStatus:
    present: bool
    verified: bool
    scope: str | None = None
    algorithm: str | None = None
    key_id: str | None = None


def add_mapping_integrity(
    payload: dict[str, object],
    signing_key: str,
    *,
    scope: str,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    sanitized = _strip_integrity(payload)
    integrity = _build_integrity_block(sanitized, signing_key, scope=scope, metadata=metadata)
    signed_payload = dict(sanitized)
    signed_payload['integrity'] = integrity
    return signed_payload


def verify_mapping_integrity(
    payload: object,
    *,
    signing_key: str | None,
    require_signature: bool = False,
) -> MappingIntegrityStatus:
    if not isinstance(payload, dict):
        if require_signature:
            raise ValueError('mapping payload is not a valid object')
        return MappingIntegrityStatus(present=False, verified=False)
    integrity = payload.get('integrity')
    if integrity is None:
        if require_signature:
            raise ValueError('mapping file is not signed')
        return MappingIntegrityStatus(present=False, verified=False)
    if not isinstance(integrity, dict):
        raise ValueError('invalid mapping integrity metadata')
    if not signing_key:
        raise ValueError('mapping file is signed; provide a signing key via --signing-key-env/--signing-key-file or a matching key registry entry')
    algorithm = str(integrity.get('algorithm', '') or INTEGRITY_ALGORITHM)
    if algorithm != INTEGRITY_ALGORITHM:
        raise ValueError(f"unsupported mapping integrity algorithm: '{algorithm}'")
    actual_mac = str(integrity.get('mac_b64', '')).strip()
    expected = _build_integrity_block(
        _strip_integrity(payload),
        signing_key,
        scope=str(integrity.get('scope', '') or 'payload'),
        metadata=None,
    )
    expected_mac = str(expected['mac_b64'])
    if not hmac.compare_digest(actual_mac, expected_mac):
        raise ValueError('invalid mapping signature or tampered mapping envelope')
    key_management = integrity.get('key_management', {})
    key_id = None
    if isinstance(key_management, dict) and key_management.get('key_id') not in (None, ''):
        key_id = str(key_management['key_id'])
    return MappingIntegrityStatus(
        present=True,
        verified=True,
        scope=str(integrity.get('scope', '') or 'payload'),
        algorithm=algorithm,
        key_id=key_id,
    )


def _build_integrity_block(
    payload: dict[str, object],
    signing_key: str,
    *,
    scope: str,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    canonical = _canonical_json(payload)
    mac = hmac.new(signing_key.encode('utf-8'), canonical, hashlib.sha256).digest()
    block: dict[str, object] = {
        'format': INTEGRITY_FORMAT,
        'scope': scope,
        'algorithm': INTEGRITY_ALGORITHM,
        'mac_b64': base64.b64encode(mac).decode('ascii'),
    }
    safe_metadata = _safe_metadata(metadata)
    if safe_metadata:
        block['key_management'] = safe_metadata
    return block


def _canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _safe_metadata(metadata: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(metadata, dict):
        return {}
    return {
        key: value
        for key, value in metadata.items()
        if key in SAFE_INTEGRITY_KEY_FIELDS and value not in (None, '')
    }


def _strip_integrity(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key != 'integrity'}
