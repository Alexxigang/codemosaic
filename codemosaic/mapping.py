from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from codemosaic.crypto import (
    DEFAULT_PROVIDER_ID,
    get_mapping_crypto_provider,
    get_provider_for_payload,
    is_encrypted_mapping_payload,
)


@dataclass(slots=True)
class MappingEntry:
    kind: str
    category: str
    original: str
    masked: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class MappingVault:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._entries: list[MappingEntry] = []
        self._original_to_masked: dict[str, str] = {}
        self._masked_to_original: dict[str, str] = {}

    def mask_identifier(self, original: str) -> str:
        return self._register('identifier', 'generic', original, 'ID_{index:04d}')

    def mask_string(self, original: str, category: str) -> str:
        normalized = category.upper()
        return self._register('string', normalized, original, f'STR_{normalized}_{{index:04d}}')

    def mask_comment(self, original: str) -> str:
        return self._register('comment', 'generic', original, 'COMMENT_{index:04d}')

    def reverse_mapping(self) -> dict[str, str]:
        return dict(self._masked_to_original)

    def save(
        self,
        path: Path,
        metadata: dict[str, object] | None = None,
        passphrase: str | None = None,
        encryption_provider: str = DEFAULT_PROVIDER_ID,
    ) -> None:
        payload = {
            'metadata': metadata or {},
            'entries': [entry.to_dict() for entry in self._entries],
            'masked_to_original': dict(self._masked_to_original),
        }
        save_mapping_payload(path, payload, passphrase=passphrase, encryption_provider=encryption_provider)

    @classmethod
    def from_file(cls, path: Path, passphrase: str | None = None) -> 'MappingVault':
        payload = load_mapping_payload(path, passphrase=passphrase)
        vault = cls()
        for item in payload.get('entries', []):
            if not isinstance(item, dict):
                continue
            entry = MappingEntry(
                kind=str(item.get('kind', 'unknown')),
                category=str(item.get('category', 'generic')),
                original=str(item.get('original', '')),
                masked=str(item.get('masked', '')),
            )
            if not entry.masked:
                continue
            vault._entries.append(entry)
            scoped_original = vault._scoped_key(entry.kind, entry.category, entry.original)
            vault._original_to_masked[scoped_original] = entry.masked
            vault._masked_to_original[entry.masked] = entry.original
        return vault

    def _register(self, kind: str, category: str, original: str, pattern: str) -> str:
        scoped_original = self._scoped_key(kind, category, original)
        if scoped_original in self._original_to_masked:
            return self._original_to_masked[scoped_original]
        counter_key = f'{kind}:{category}'
        self._counters[counter_key] = self._counters.get(counter_key, 0) + 1
        masked = pattern.format(index=self._counters[counter_key])
        entry = MappingEntry(kind=kind, category=category, original=original, masked=masked)
        self._entries.append(entry)
        self._original_to_masked[scoped_original] = masked
        self._masked_to_original[masked] = original
        return masked

    @staticmethod
    def _scoped_key(kind: str, category: str, original: str) -> str:
        return f'{kind}:{category}:{original}'



def load_mapping_payload(path: Path, passphrase: str | None = None) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if is_encrypted_mapping_payload(payload):
        if not passphrase:
            raise ValueError('mapping file is encrypted; provide a passphrase via --passphrase-env or --passphrase-file')
        decrypted = get_provider_for_payload(payload).decrypt(payload, passphrase)
        parsed = json.loads(decrypted.decode('utf-8'))
        return parsed if isinstance(parsed, dict) else {}
    return payload if isinstance(payload, dict) else {}



def save_mapping_payload(
    path: Path,
    payload: dict[str, object],
    passphrase: str | None = None,
    encryption_provider: str = DEFAULT_PROVIDER_ID,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    if passphrase:
        provider = get_mapping_crypto_provider(encryption_provider)
        envelope = provider.encrypt(serialized.encode('utf-8'), passphrase)
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding='utf-8')
        return
    path.write_text(serialized, encoding='utf-8')



def rewrap_mapping_file(
    path: Path,
    output_path: Path | None = None,
    passphrase: str | None = None,
    new_passphrase: str | None = None,
    encryption_provider: str | None = None,
) -> Path:
    raw_payload = json.loads(path.read_text(encoding='utf-8'))
    payload = load_mapping_payload(path, passphrase=passphrase)
    destination = output_path or path
    selected_provider = _resolve_output_provider(raw_payload, encryption_provider)
    save_mapping_payload(destination, payload, passphrase=new_passphrase, encryption_provider=selected_provider)
    return destination



def _resolve_output_provider(raw_payload: object, encryption_provider: str | None) -> str:
    if encryption_provider:
        return encryption_provider
    if is_encrypted_mapping_payload(raw_payload):
        return get_provider_for_payload(raw_payload).provider_id
    return DEFAULT_PROVIDER_ID
