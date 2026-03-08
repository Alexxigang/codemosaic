from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codemosaic.mapping import MappingVault, load_mapping_payload, rewrap_mapping_file
from codemosaic.patching import load_reverse_mapping, translate_patch_text


class EncryptedMappingTests(unittest.TestCase):
    def test_encrypted_mapping_round_trip_requires_passphrase(self) -> None:
        vault = MappingVault()
        vault.mask_identifier("revenueModel")
        vault.mask_string("https://internal.example.com", "url")
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / "mapping.enc.json"
            vault.save(mapping_path, metadata={"encrypted": True}, passphrase="secret-passphrase")
            with self.assertRaises(ValueError):
                load_mapping_payload(mapping_path)
            payload = load_mapping_payload(mapping_path, passphrase="secret-passphrase")
            self.assertIn("masked_to_original", payload)
            reverse = load_reverse_mapping(mapping_path, passphrase="secret-passphrase")
            self.assertIn("revenueModel", reverse.values())

    def test_patch_translation_works_with_encrypted_mapping(self) -> None:
        vault = MappingVault()
        masked_identifier = vault.mask_identifier("revenueModel")
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / "mapping.enc.json"
            vault.save(mapping_path, passphrase="secret-passphrase")
            translated = translate_patch_text(
                f"- {masked_identifier}\n",
                load_reverse_mapping(mapping_path, passphrase="secret-passphrase"),
            )
            self.assertIn("revenueModel", translated)

    def test_wrong_passphrase_fails(self) -> None:
        vault = MappingVault()
        vault.mask_identifier("apiSecret")
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / "mapping.enc.json"
            vault.save(mapping_path, passphrase="secret-passphrase")
            with self.assertRaises(ValueError):
                load_reverse_mapping(mapping_path, passphrase="wrong-passphrase")

    def test_rekey_mapping_rotates_passphrase(self) -> None:
        vault = MappingVault()
        vault.mask_identifier("riskEngine")
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "mapping.enc.json"
            rotated_path = Path(temp_dir) / "mapping.rotated.enc.json"
            vault.save(original_path, passphrase="old-passphrase")
            rewrap_mapping_file(
                original_path,
                output_path=rotated_path,
                passphrase="old-passphrase",
                new_passphrase="new-passphrase",
            )
            with self.assertRaises(ValueError):
                load_mapping_payload(rotated_path, passphrase="old-passphrase")
            payload = load_mapping_payload(rotated_path, passphrase="new-passphrase")
            self.assertEqual(payload["masked_to_original"]["ID_0001"], "riskEngine")

    def test_rekey_mapping_can_encrypt_plain_mapping(self) -> None:
        vault = MappingVault()
        vault.mask_identifier("billingAdapter")
        with tempfile.TemporaryDirectory() as temp_dir:
            plain_path = Path(temp_dir) / "mapping.json"
            encrypted_path = Path(temp_dir) / "mapping.enc.json"
            vault.save(plain_path)
            rewrap_mapping_file(plain_path, output_path=encrypted_path, new_passphrase="secret-passphrase")
            with self.assertRaises(ValueError):
                load_mapping_payload(encrypted_path)
            payload = load_mapping_payload(encrypted_path, passphrase="secret-passphrase")
            self.assertEqual(payload["masked_to_original"]["ID_0001"], "billingAdapter")

    def test_rekey_mapping_can_decrypt_to_plaintext(self) -> None:
        vault = MappingVault()
        vault.mask_identifier("authGateway")
        with tempfile.TemporaryDirectory() as temp_dir:
            encrypted_path = Path(temp_dir) / "mapping.enc.json"
            plain_path = Path(temp_dir) / "mapping.json"
            vault.save(encrypted_path, passphrase="secret-passphrase")
            rewrap_mapping_file(encrypted_path, output_path=plain_path, passphrase="secret-passphrase")
            payload = load_mapping_payload(plain_path)
            self.assertEqual(payload["masked_to_original"]["ID_0001"], "authGateway")


if __name__ == "__main__":
    unittest.main()
