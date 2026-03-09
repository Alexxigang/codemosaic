from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from codemosaic.crypto import MANAGED_PROVIDER_ID
from codemosaic.key_management import generate_mapping_key
from codemosaic.mapping import MappingVault, load_mapping_payload
from codemosaic.policy import load_policy


class KeyManagementTests(unittest.TestCase):
    def test_policy_loads_key_management_and_defaults_to_managed_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / 'policy.yaml'
            policy_path.write_text(
                'mapping:\n'
                '  require_encryption: true\n'
                '  key_management:\n'
                '    source: env\n'
                '    reference: CODEMOSAIC_MAPPING_KEY\n'
                '    key_id: team-dev-v1\n',
                encoding='utf-8',
            )
            policy = load_policy(policy_path)
            self.assertEqual(policy.mapping.key_management.source, 'env')
            self.assertEqual(policy.mapping.key_management.reference, 'CODEMOSAIC_MAPPING_KEY')
            self.assertEqual(policy.mapping.key_management.key_id, 'team-dev-v1')
            resolved = policy.resolve_mapping_policy(['src/secret/app.py'])
            self.assertTrue(resolved.require_encryption)
            self.assertEqual(resolved.encryption_provider, MANAGED_PROVIDER_ID)

    def test_managed_provider_round_trip_and_header_metadata(self) -> None:
        vault = MappingVault()
        vault.mask_identifier('tradeEngine')
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / 'mapping.enc.json'
            key_value = generate_mapping_key()
            vault.save(
                mapping_path,
                metadata={
                    'run_id': 'demo-run',
                    'generated_at': '2026-03-09T10:00:00',
                    'encryption_provider': MANAGED_PROVIDER_ID,
                    'key_management': {
                        'source': 'env',
                        'reference': 'CODEMOSAIC_MAPPING_KEY',
                        'key_id': 'team-a-v1',
                        'origin': 'policy',
                    },
                },
                passphrase=key_value,
                encryption_provider=MANAGED_PROVIDER_ID,
            )
            envelope = json.loads(mapping_path.read_text(encoding='utf-8'))
            self.assertEqual(envelope['provider'], MANAGED_PROVIDER_ID)
            self.assertEqual(envelope['header']['key_management']['key_id'], 'team-a-v1')
            payload = load_mapping_payload(mapping_path, passphrase=key_value)
            self.assertEqual(payload['masked_to_original']['ID_0001'], 'tradeEngine')

    def test_cli_mask_uses_policy_managed_key_from_env(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            output_root = Path(temp_dir) / 'repo.masked'
            (workspace / 'src').mkdir(parents=True)
            (workspace / 'src' / 'app.py').write_text('revenue_model = 1\n', encoding='utf-8')
            policy_path = workspace / 'policy.yaml'
            policy_path.write_text(
                'mapping:\n'
                '  require_encryption: true\n'
                '  encryption_provider: managed-v1\n'
                '  key_management:\n'
                '    source: env\n'
                '    reference: CODEMOSAIC_MAPPING_KEY\n'
                '    key_id: team-dev-v1\n',
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
            runs_root = workspace / '.codemosaic' / 'runs'
            mapping_files = list(runs_root.rglob('mapping.enc.json'))
            self.assertEqual(len(mapping_files), 1)
            envelope = json.loads(mapping_files[0].read_text(encoding='utf-8'))
            self.assertEqual(envelope['provider'], MANAGED_PROVIDER_ID)
            self.assertEqual(envelope['header']['key_management']['key_id'], 'team-dev-v1')
            payload = load_mapping_payload(mapping_files[0], passphrase=env['CODEMOSAIC_MAPPING_KEY'])
            metadata = payload['metadata']['key_management']
            self.assertEqual(metadata['source'], 'env')
            self.assertEqual(metadata['reference'], 'CODEMOSAIC_MAPPING_KEY')
            self.assertEqual(metadata['key_id'], 'team-dev-v1')
            self.assertEqual(metadata['origin'], 'policy')

    def test_generate_key_command_writes_file(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / 'mapping.key'
            subprocess.run(
                ['python', '-m', 'codemosaic', 'generate-key', '--output', str(output_file)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            value = output_file.read_text(encoding='utf-8').strip()
            self.assertTrue(value.startswith('base64:'))


if __name__ == '__main__':
    unittest.main()
