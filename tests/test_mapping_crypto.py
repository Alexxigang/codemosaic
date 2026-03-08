from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codemosaic.crypto import (
    DEFAULT_PROVIDER_ID,
    describe_mapping_crypto_providers,
    get_mapping_crypto_provider,
    list_mapping_crypto_providers,
)
from codemosaic.mapping import MappingVault, load_mapping_payload, rewrap_mapping_file


class MappingCryptoProviderTests(unittest.TestCase):
    def test_default_provider_is_registered(self) -> None:
        self.assertIn(DEFAULT_PROVIDER_ID, list_mapping_crypto_providers())
        provider = get_mapping_crypto_provider()
        self.assertEqual(provider.provider_id, DEFAULT_PROVIDER_ID)

    def test_provider_descriptions_include_default(self) -> None:
        descriptions = describe_mapping_crypto_providers()
        self.assertTrue(any(item['provider_id'] == DEFAULT_PROVIDER_ID and item['default'] for item in descriptions))

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_mapping_crypto_provider('missing-provider')

    def test_encrypted_mapping_persists_provider_metadata(self) -> None:
        vault = MappingVault()
        vault.mask_identifier('ledgerService')
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / 'mapping.enc.json'
            vault.save(mapping_path, passphrase='secret-passphrase', encryption_provider=DEFAULT_PROVIDER_ID)
            envelope = json.loads(mapping_path.read_text(encoding='utf-8'))
            self.assertEqual(envelope['provider'], DEFAULT_PROVIDER_ID)
            payload = load_mapping_payload(mapping_path, passphrase='secret-passphrase')
            self.assertEqual(payload['masked_to_original']['ID_0001'], 'ledgerService')

    def test_rewrap_rejects_unknown_output_provider(self) -> None:
        vault = MappingVault()
        vault.mask_identifier('opsConsole')
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / 'mapping.json'
            vault.save(mapping_path)
            with self.assertRaises(ValueError):
                rewrap_mapping_file(mapping_path, new_passphrase='secret-passphrase', encryption_provider='missing-provider')


if __name__ == '__main__':
    unittest.main()
