from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codemosaic.mapping import MappingVault
from codemosaic.patching import load_reverse_mapping, translate_patch_text


class PatchTranslationTests(unittest.TestCase):
    def test_patch_translation_restores_original_tokens(self) -> None:
        vault = MappingVault()
        masked_identifier = vault.mask_identifier("compute_revenue")
        masked_string = vault.mask_string("https://internal.example.com", "url")
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / "mapping.json"
            vault.save(mapping_path)
            translated = translate_patch_text(
                f"- {masked_identifier}\n+ {masked_string}\n",
                load_reverse_mapping(mapping_path),
            )
            self.assertIn("compute_revenue", translated)
            self.assertIn("https://internal.example.com", translated)


if __name__ == "__main__":
    unittest.main()
