from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from codemosaic.key_management import generate_mapping_key
from codemosaic.mapping import MappingVault, verify_mapping_file
from codemosaic.policy import load_policy


class MappingIntegrityTests(unittest.TestCase):
    def test_signed_encrypted_mapping_verifies_and_detects_tamper(self) -> None:
        vault = MappingVault()
        vault.mask_identifier('pricingEngine')
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / 'mapping.enc.json'
            vault.save(
                mapping_path,
                metadata={'run_id': 'signed-run'},
                passphrase=generate_mapping_key(),
                signing_key='audit-signing-key',
                signing_metadata={'key_id': 'audit-2026q1', 'source': 'env', 'reference': 'CODEMOSAIC_AUDIT_KEY'},
            )
            status = verify_mapping_file(mapping_path, signing_key='audit-signing-key', require_signature=True)
            self.assertTrue(status.present)
            self.assertTrue(status.verified)
            self.assertEqual(status.scope, 'envelope')
            self.assertEqual(status.key_id, 'audit-2026q1')

            envelope = json.loads(mapping_path.read_text(encoding='utf-8'))
            envelope['header']['run_id'] = 'tampered-run'
            mapping_path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_mapping_file(mapping_path, signing_key='audit-signing-key', require_signature=True)

    def test_signed_plain_mapping_verifies(self) -> None:
        vault = MappingVault()
        vault.mask_identifier('ledgerWorker')
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / 'mapping.json'
            vault.save(mapping_path, signing_key='plain-signing-key', signing_metadata={'key_id': 'plain-audit'})
            status = verify_mapping_file(mapping_path, signing_key='plain-signing-key', require_signature=True)
            self.assertTrue(status.present)
            self.assertTrue(status.verified)
            self.assertEqual(status.scope, 'payload')
            self.assertEqual(status.key_id, 'plain-audit')

    def test_cli_verify_mapping_reports_signed_status(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / 'mapping.json'
            vault = MappingVault()
            vault.mask_identifier('tradeGateway')
            vault.save(mapping_path, signing_key='cli-audit-key', signing_metadata={'key_id': 'cli-audit'})
            env = os.environ.copy()
            env['CODEMOSAIC_AUDIT_KEY'] = 'cli-audit-key'
            result = subprocess.run(
                ['python', '-m', 'codemosaic', 'verify-mapping', str(mapping_path), '--signing-key-env', 'CODEMOSAIC_AUDIT_KEY', '--require-signature'],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            self.assertIn('signed: yes', result.stdout)
            self.assertIn('verified: yes', result.stdout)
            self.assertIn('key id: cli-audit', result.stdout)


    def test_cli_mask_uses_policy_signature_key_from_env(self) -> None:
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
                '    key_id: team-dev-v1\n'
                '  signature_management:\n'
                '    source: env\n'
                '    reference: CODEMOSAIC_AUDIT_KEY\n'
                '    key_id: audit-2026q1\n',
                encoding='utf-8',
            )
            env = os.environ.copy()
            env['CODEMOSAIC_MAPPING_KEY'] = generate_mapping_key()
            env['CODEMOSAIC_AUDIT_KEY'] = 'policy-audit-key'
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
            self.assertEqual(envelope['integrity']['key_management']['key_id'], 'audit-2026q1')
            self.assertEqual(envelope['header']['signature_management']['key_id'], 'audit-2026q1')
            status = verify_mapping_file(mapping_files[0], signing_key='policy-audit-key', require_signature=True)
            self.assertTrue(status.verified)

    def test_policy_loads_signature_management_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / 'policy.yaml'
            policy_path.write_text(
                'mapping:\n'
                '  require_encryption: true\n'
                '  signature_management:\n'
                '    source: env\n'
                '    reference: CODEMOSAIC_AUDIT_KEY\n'
                '    key_id: audit-2026q1\n',
                encoding='utf-8',
            )
            policy = load_policy(policy_path)
            self.assertEqual(policy.mapping.signature_management.source, 'env')
            self.assertEqual(policy.mapping.signature_management.reference, 'CODEMOSAIC_AUDIT_KEY')
            self.assertEqual(policy.mapping.signature_management.key_id, 'audit-2026q1')


if __name__ == '__main__':
    unittest.main()
