from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codemosaic.policy import load_policy


class CliWorkspaceSetupTests(unittest.TestCase):
    def test_setup_workspace_bootstraps_policy_registry_and_keys(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            source_dir = workspace / 'src'
            source_dir.mkdir(parents=True)
            (source_dir / 'app.py').write_text('print("hello")\n', encoding='utf-8')

            result = subprocess.run(
                [
                    'python', '-m', 'codemosaic', 'setup-workspace', str(workspace),
                    '--preset', 'balanced-ai-gateway',
                    '--key-prefix', 'team-dev',
                ],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertIn('policy file:', result.stdout)
            self.assertIn('mapping key id: team-dev-mapping', result.stdout)
            self.assertIn('signing key id: team-dev-signing', result.stdout)

            policy_path = workspace / 'policy.codemosaic.yaml'
            registry_path = workspace / '.codemosaic' / 'key-registry.json'
            mapping_key_file = workspace / '.codemosaic' / 'keys' / 'team-dev-mapping.key'
            signing_key_file = workspace / '.codemosaic' / 'keys' / 'team-dev-signing.key'

            self.assertTrue(policy_path.exists())
            self.assertTrue(registry_path.exists())
            self.assertTrue(mapping_key_file.exists())
            self.assertTrue(signing_key_file.exists())

            policy = load_policy(policy_path)
            self.assertTrue(policy.mapping.require_encryption)
            self.assertEqual(policy.mapping.encryption_provider, 'managed-v1')
            self.assertEqual(policy.mapping.key_management.key_id, 'team-dev-mapping')
            self.assertEqual(policy.mapping.signature_management.key_id, 'team-dev-signing')
            self.assertEqual(policy.mapping.key_management.registry_file, '.codemosaic/key-registry.json')
            self.assertTrue(policy.mapping.require_signature_for_unmask)

            mask_output = workspace.with_name('repo.masked')
            subprocess.run(
                ['python', '-m', 'codemosaic', 'mask', str(workspace), '--policy', str(policy_path), '--output', str(mask_output)],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            mapping_files = list((workspace / '.codemosaic' / 'runs').glob('*/mapping.enc.json'))
            self.assertTrue(mapping_files)

    def test_setup_workspace_can_skip_signing_key(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            workspace.mkdir(parents=True)
            subprocess.run(
                [
                    'python', '-m', 'codemosaic', 'setup-workspace', str(workspace),
                    '--without-signing-key',
                    '--key-prefix', 'demo',
                ],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            policy = load_policy(workspace / 'policy.codemosaic.yaml')
            self.assertFalse(policy.mapping.require_signature_for_unmask)
            self.assertEqual(policy.mapping.key_management.key_id, 'demo-mapping')
            self.assertIsNone(policy.mapping.signature_management.key_id)
            self.assertFalse((workspace / '.codemosaic' / 'keys' / 'demo-signing.key').exists())


if __name__ == '__main__':
    unittest.main()
