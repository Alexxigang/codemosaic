from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from codemosaic.mapping import MappingVault, load_mapping_payload
from codemosaic.runs import list_run_mappings, rekey_run_mappings


class RunMappingsTests(unittest.TestCase):
    def test_list_run_mappings_sorts_latest_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            runs_root = workspace / '.codemosaic' / 'runs'
            older = runs_root / 'older'
            newer = runs_root / 'newer'
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            vault = MappingVault()
            vault.mask_identifier('alphaService')
            vault.save(older / 'mapping.json')
            vault = MappingVault()
            vault.mask_identifier('betaService')
            vault.save(newer / 'mapping.json')
            os.utime(older / 'mapping.json', (1000, 1000))
            os.utime(newer / 'mapping.json', (2000, 2000))

            items = list_run_mappings(workspace)

            self.assertEqual([item.run_id for item in items], ['newer', 'older'])

    def test_rekey_run_mappings_honors_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            runs_root = workspace / '.codemosaic' / 'runs'
            older = runs_root / 'older'
            newer = runs_root / 'newer'
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            vault = MappingVault()
            vault.mask_identifier('alphaService')
            vault.save(older / 'mapping.enc.json', passphrase='old-passphrase')
            vault = MappingVault()
            vault.mask_identifier('betaService')
            vault.save(newer / 'mapping.enc.json', passphrase='old-passphrase')
            os.utime(older / 'mapping.enc.json', (1000, 1000))
            os.utime(newer / 'mapping.enc.json', (2000, 2000))

            outputs = rekey_run_mappings(
                workspace,
                passphrase='old-passphrase',
                new_passphrase='new-passphrase',
                limit=1,
            )

            self.assertEqual(len(outputs), 1)
            with self.assertRaises(ValueError):
                load_mapping_payload(newer / 'mapping.enc.json', passphrase='old-passphrase')
            payload = load_mapping_payload(newer / 'mapping.enc.json', passphrase='new-passphrase')
            self.assertEqual(payload['masked_to_original']['ID_0001'], 'betaService')
            older_payload = load_mapping_payload(older / 'mapping.enc.json', passphrase='old-passphrase')
            self.assertEqual(older_payload['masked_to_original']['ID_0001'], 'alphaService')


if __name__ == '__main__':
    unittest.main()
