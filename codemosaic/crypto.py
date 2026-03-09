from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol


ENCRYPTED_FORMAT = 'codemosaic-mapping-v1'
DEFAULT_PROVIDER_ID = 'prototype-v1'
MANAGED_PROVIDER_ID = 'managed-v1'
KDF_ITERATIONS = 390000
AAD = b'codemosaic'


class MappingCryptoProvider(Protocol):
    provider_id: str
    algorithm_name: str
    source: str

    def encrypt(self, plaintext: bytes, passphrase: str) -> dict[str, object]: ...

    def decrypt(self, payload: dict[str, object], passphrase: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class PrototypeMappingCryptoProvider:
    provider_id: str = DEFAULT_PROVIDER_ID
    algorithm_name: str = 'PBKDF2-HMAC-SHA256+HMAC-SHA256-XORSTREAM'
    source: str = 'built-in'

    def encrypt(self, plaintext: bytes, passphrase: str) -> dict[str, object]:
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(16)
        encryption_key, mac_key = _derive_keys(passphrase, salt, KDF_ITERATIONS)
        ciphertext = _xor_with_keystream(plaintext, encryption_key, nonce)
        mac = hmac.new(mac_key, AAD + salt + nonce + ciphertext, hashlib.sha256).digest()
        return {
            'format': ENCRYPTED_FORMAT,
            'provider': self.provider_id,
            'algorithm': self.algorithm_name,
            'kdf': {
                'name': 'PBKDF2-HMAC-SHA256',
                'salt_b64': _b64encode(salt),
                'iterations': KDF_ITERATIONS,
            },
            'nonce_b64': _b64encode(nonce),
            'ciphertext_b64': _b64encode(ciphertext),
            'mac_b64': _b64encode(mac),
        }

    def decrypt(self, payload: dict[str, object], passphrase: str) -> bytes:
        kdf = payload.get('kdf', {})
        if not isinstance(kdf, dict):
            raise ValueError('invalid encrypted mapping metadata')
        salt = _b64decode(str(kdf.get('salt_b64', '')))
        iterations = int(kdf.get('iterations', KDF_ITERATIONS))
        nonce = _b64decode(str(payload.get('nonce_b64', '')))
        ciphertext = _b64decode(str(payload.get('ciphertext_b64', '')))
        mac = _b64decode(str(payload.get('mac_b64', '')))
        encryption_key, mac_key = _derive_keys(passphrase, salt, iterations)
        expected_mac = hmac.new(mac_key, AAD + salt + nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError('invalid mapping passphrase or corrupted encrypted mapping')
        return _xor_with_keystream(ciphertext, encryption_key, nonce)


@dataclass(frozen=True, slots=True)
class ManagedKeyMappingCryptoProvider:
    provider_id: str = MANAGED_PROVIDER_ID
    algorithm_name: str = 'HKDF-SHA256+HMAC-SHA256-XORSTREAM'
    source: str = 'built-in'

    def encrypt(self, plaintext: bytes, passphrase: str) -> dict[str, object]:
        master_key = _decode_managed_key(passphrase)
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(16)
        encryption_key, mac_key = _derive_managed_keys(master_key, salt)
        ciphertext = _xor_with_keystream(plaintext, encryption_key, nonce)
        mac = hmac.new(mac_key, AAD + salt + nonce + ciphertext, hashlib.sha256).digest()
        return {
            'format': ENCRYPTED_FORMAT,
            'provider': self.provider_id,
            'algorithm': self.algorithm_name,
            'kdf': {
                'name': 'HKDF-SHA256',
                'salt_b64': _b64encode(salt),
            },
            'nonce_b64': _b64encode(nonce),
            'ciphertext_b64': _b64encode(ciphertext),
            'mac_b64': _b64encode(mac),
        }

    def decrypt(self, payload: dict[str, object], passphrase: str) -> bytes:
        kdf = payload.get('kdf', {})
        if not isinstance(kdf, dict):
            raise ValueError('invalid encrypted mapping metadata')
        salt = _b64decode(str(kdf.get('salt_b64', '')))
        nonce = _b64decode(str(payload.get('nonce_b64', '')))
        ciphertext = _b64decode(str(payload.get('ciphertext_b64', '')))
        mac = _b64decode(str(payload.get('mac_b64', '')))
        master_key = _decode_managed_key(passphrase)
        encryption_key, mac_key = _derive_managed_keys(master_key, salt)
        expected_mac = hmac.new(mac_key, AAD + salt + nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError('invalid mapping key or corrupted encrypted mapping')
        return _xor_with_keystream(ciphertext, encryption_key, nonce)


@dataclass(frozen=True, slots=True)
class AesGcmMappingCryptoProvider:
    provider_id: str = 'aesgcm-v1'
    algorithm_name: str = 'AES-256-GCM+PBKDF2-HMAC-SHA256'
    source: str = 'optional:cryptography'

    def encrypt(self, plaintext: bytes, passphrase: str) -> dict[str, object]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        key = hashlib.pbkdf2_hmac('sha256', passphrase.encode('utf-8'), salt, KDF_ITERATIONS, dklen=32)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)
        return {
            'format': ENCRYPTED_FORMAT,
            'provider': self.provider_id,
            'algorithm': self.algorithm_name,
            'kdf': {
                'name': 'PBKDF2-HMAC-SHA256',
                'salt_b64': _b64encode(salt),
                'iterations': KDF_ITERATIONS,
            },
            'nonce_b64': _b64encode(nonce),
            'ciphertext_b64': _b64encode(ciphertext),
        }

    def decrypt(self, payload: dict[str, object], passphrase: str) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        kdf = payload.get('kdf', {})
        if not isinstance(kdf, dict):
            raise ValueError('invalid encrypted mapping metadata')
        salt = _b64decode(str(kdf.get('salt_b64', '')))
        iterations = int(kdf.get('iterations', KDF_ITERATIONS))
        nonce = _b64decode(str(payload.get('nonce_b64', '')))
        ciphertext = _b64decode(str(payload.get('ciphertext_b64', '')))
        key = hashlib.pbkdf2_hmac('sha256', passphrase.encode('utf-8'), salt, iterations, dklen=32)
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, AAD)
        except Exception as exc:
            raise ValueError('invalid mapping passphrase or corrupted encrypted mapping') from exc



def _build_provider_registry() -> dict[str, MappingCryptoProvider]:
    providers: dict[str, MappingCryptoProvider] = {
        DEFAULT_PROVIDER_ID: PrototypeMappingCryptoProvider(),
        MANAGED_PROVIDER_ID: ManagedKeyMappingCryptoProvider(),
    }
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _  # noqa: F401
    except Exception:
        return providers
    providers['aesgcm-v1'] = AesGcmMappingCryptoProvider()
    return providers


_PROVIDER_REGISTRY = _build_provider_registry()


def list_mapping_crypto_providers() -> list[str]:
    return sorted(_PROVIDER_REGISTRY)



def describe_mapping_crypto_providers() -> list[dict[str, str | bool]]:
    descriptions: list[dict[str, str | bool]] = []
    for provider_id in list_mapping_crypto_providers():
        provider = _PROVIDER_REGISTRY[provider_id]
        descriptions.append(
            {
                'provider_id': provider.provider_id,
                'algorithm': provider.algorithm_name,
                'source': provider.source,
                'default': provider.provider_id == DEFAULT_PROVIDER_ID,
            }
        )
    return descriptions



def get_mapping_crypto_provider(provider_id: str | None = None) -> MappingCryptoProvider:
    selected = provider_id or DEFAULT_PROVIDER_ID
    provider = _PROVIDER_REGISTRY.get(selected)
    if provider is None:
        raise ValueError(f"unknown mapping encryption provider: '{selected}'")
    return provider



def get_provider_for_payload(payload: dict[str, object]) -> MappingCryptoProvider:
    provider_id = str(payload.get('provider') or DEFAULT_PROVIDER_ID)
    return get_mapping_crypto_provider(provider_id)



def is_encrypted_mapping_payload(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get('format') == ENCRYPTED_FORMAT



def _derive_keys(passphrase: str, salt: bytes, iterations: int) -> tuple[bytes, bytes]:
    material = hashlib.pbkdf2_hmac('sha256', passphrase.encode('utf-8'), salt, iterations, dklen=64)
    return material[:32], material[32:]



def _derive_managed_keys(master_key: bytes, salt: bytes) -> tuple[bytes, bytes]:
    material = _hkdf_sha256(master_key, salt=salt, info=AAD + b':managed', length=64)
    return material[:32], material[32:]



def _hkdf_sha256(input_key_material: bytes, *, salt: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(salt or (b'\x00' * hashlib.sha256().digest_size), input_key_material, hashlib.sha256).digest()
    output = bytearray()
    block = b''
    counter = 1
    while len(output) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        output.extend(block)
        counter += 1
    return bytes(output[:length])



def _xor_with_keystream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    output = bytearray(len(data))
    counter = 0
    offset = 0
    while offset < len(data):
        counter_bytes = counter.to_bytes(8, 'big')
        block = hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest()
        block_length = min(len(block), len(data) - offset)
        for index in range(block_length):
            output[offset + index] = data[offset + index] ^ block[index]
        offset += block_length
        counter += 1
    return bytes(output)



def _decode_managed_key(value: str) -> bytes:
    normalized = value.strip()
    if normalized.startswith('base64:'):
        raw = _urlsafe_b64decode(normalized.removeprefix('base64:'))
    elif normalized.startswith('hex:'):
        try:
            raw = bytes.fromhex(normalized.removeprefix('hex:'))
        except ValueError as exc:
            raise ValueError('invalid managed mapping key encoding') from exc
    else:
        try:
            raw = _urlsafe_b64decode(normalized)
        except ValueError:
            raw = normalized.encode('utf-8')
    if len(raw) < 32:
        raise ValueError('managed mapping key must decode to at least 32 bytes')
    return raw



def _urlsafe_b64decode(value: str) -> bytes:
    padded = value + '=' * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode('ascii'))
    except Exception as exc:
        raise ValueError('invalid managed mapping key encoding') from exc



def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode('ascii')



def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode('ascii'), validate=True)
    except Exception as exc:
        raise ValueError('invalid encrypted mapping encoding') from exc
