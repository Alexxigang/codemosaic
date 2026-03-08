from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from codemosaic.mapping import MappingVault, load_mapping_payload


class CliRekeyRunsTests(unittest.TestCase):
    def test_rekey_runs_rotates_latest_mapping(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
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

            env = os.environ.copy()
            env['OLD_CODEMOSAIC_PASSPHRASE'] = 'old-passphrase'
            env['NEW_CODEMOSAIC_PASSPHRASE'] = 'new-passphrase'
            result = subprocess.run(
                [
                    'python',
                    '-m',
                    'codemosaic',
                    'rekey-runs',
                    str(workspace),
                    '--limit',
                    '1',
                    '--passphrase-env',
                    'OLD_CODEMOSAIC_PASSPHRASE',
                    '--new-passphrase-env',
                    'NEW_CODEMOSAIC_PASSPHRASE',
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )

            self.assertIn('rekeyed runs: 1', result.stdout)
            with self.assertRaises(ValueError):
                load_mapping_payload(newer / 'mapping.enc.json', passphrase='old-passphrase')
            payload = load_mapping_payload(newer / 'mapping.enc.json', passphrase='new-passphrase')
            self.assertEqual(payload['masked_to_original']['ID_0001'], 'betaService')
            older_payload = load_mapping_payload(older / 'mapping.enc.json', passphrase='old-passphrase')
            self.assertEqual(older_payload['masked_to_original']['ID_0001'], 'alphaService')


if __name__ == '__main__':
    unittest.main()
