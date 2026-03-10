from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from codemosaic.key_management import (
    default_key_registry_path,
    find_registered_key_source,
    generate_mapping_key,
    load_key_registry,
    register_key_source,
)
from codemosaic.mapping import load_mapping_payload


class KeyRegistryTests(unittest.TestCase):
    def test_register_and_find_key_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            workspace.mkdir(parents=True)
            registry_path = default_key_registry_path(workspace)
            register_key_source(
                registry_path,
                key_id='team-dev-2026q1',
                source='env',
                reference='CODEMOSAIC_MAPPING_KEY',
            )
            entry = find_registered_key_source(registry_path, 'team-dev-2026q1')
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.source, 'env')
            self.assertEqual(entry.reference, 'CODEMOSAIC_MAPPING_KEY')
            self.assertEqual(load_key_registry(registry_path)[0].key_id, 'team-dev-2026q1')

    def test_cli_register_and_list_key_sources(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            workspace.mkdir(parents=True)
            subprocess.run(
                [
                    'python', '-m', 'codemosaic', 'register-key-source', str(workspace),
                    '--key-id', 'team-dev-2026q1',
                    '--source', 'env',
                    '--reference', 'CODEMOSAIC_MAPPING_KEY',
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            result = subprocess.run(
                ['python', '-m', 'codemosaic', 'list-key-sources', str(workspace)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn('registered keys: 1', result.stdout)
            self.assertIn('team-dev-2026q1', result.stdout)
            self.assertIn('CODEMOSAIC_MAPPING_KEY', result.stdout)

    def test_mask_resolves_key_id_via_registry(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            output_root = Path(temp_dir) / 'repo.masked'
            (workspace / 'src').mkdir(parents=True)
            (workspace / 'src' / 'app.py').write_text('billing_adapter = 1\n', encoding='utf-8')
            register_key_source(
                default_key_registry_path(workspace),
                key_id='team-dev-2026q1',
                source='env',
                reference='CODEMOSAIC_MAPPING_KEY',
            )
            policy_path = workspace / 'policy.yaml'
            policy_path.write_text(
                'mapping:\n'
                '  require_encryption: true\n'
                '  key_management:\n'
                '    key_id: team-dev-2026q1\n',
                encoding='utf-8',
            )
            env = os.environ.copy()
            env['CODEMOSAIC_MAPPING_KEY'] = generate_mapping_key()
            subprocess.run(
                ['python', '-m', 'codemosaic', 'mask', str(workspace), '--policy', str(policy_path), '--output', str(output_root)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            mapping_files = list((workspace / '.codemosaic' / 'runs').rglob('mapping.enc.json'))
            self.assertEqual(len(mapping_files), 1)
            envelope = json.loads(mapping_files[0].read_text(encoding='utf-8'))
            self.assertEqual(envelope['header']['key_management']['key_id'], 'team-dev-2026q1')
            payload = load_mapping_payload(mapping_files[0], passphrase=env['CODEMOSAIC_MAPPING_KEY'])
            self.assertEqual(payload['metadata']['key_management']['origin'], 'registry')
            self.assertIn('key-registry.json', payload['metadata']['key_management']['registry_path'])


if __name__ == '__main__':
    unittest.main()
