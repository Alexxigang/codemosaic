from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from codemosaic.mapping import MappingVault, load_mapping_payload
from codemosaic.runs import audit_run_mappings, list_run_mappings, rekey_run_mappings


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


    def test_audit_run_mappings_reports_signature_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            runs_root = workspace / '.codemosaic' / 'runs'
            unsigned = runs_root / 'unsigned'
            signed = runs_root / 'signed'
            unsigned.mkdir(parents=True)
            signed.mkdir(parents=True)

            unsigned_vault = MappingVault()
            unsigned_vault.mask_identifier('alphaService')
            unsigned_vault.save(unsigned / 'mapping.json')
            (unsigned / 'report.json').write_text(json.dumps({'files': [{}, {}]}), encoding='utf-8')

            signed_vault = MappingVault()
            signed_vault.mask_identifier('betaService')
            signed_vault.save(
                signed / 'mapping.enc.json',
                metadata={'generated_at': '2026-03-10T08:00:00', 'encryption_provider': 'managed-v1'},
                passphrase='managed-key',
                signing_key='audit-key',
                signing_metadata={'key_id': 'audit-2026q1'},
            )
            (signed / 'report.json').write_text(json.dumps({'files': [{}, {}, {}], 'source_root': 'repo', 'output_root': 'repo.masked'}), encoding='utf-8')
            os.utime(unsigned / 'mapping.json', (1000, 1000))
            os.utime(signed / 'mapping.enc.json', (2000, 2000))

            records = audit_run_mappings(workspace, signing_key='audit-key')

            self.assertEqual([record.run_id for record in records], ['signed', 'unsigned'])
            self.assertEqual(records[0].verification_status, 'verified')
            self.assertTrue(records[0].signed)
            self.assertEqual(records[0].signature_key_id, 'audit-2026q1')
            self.assertEqual(records[0].file_count, 3)
            self.assertEqual(records[1].verification_status, 'unsigned')
            self.assertFalse(records[1].signed)

    def test_cli_audit_runs_writes_json_report(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            run_dir = workspace / '.codemosaic' / 'runs' / 'signed'
            run_dir.mkdir(parents=True)
            report_path = Path(temp_dir) / 'audit.json'
            vault = MappingVault()
            vault.mask_identifier('gammaService')
            vault.save(
                run_dir / 'mapping.json',
                metadata={'generated_at': '2026-03-10T08:00:00'},
                signing_key='cli-audit-key',
                signing_metadata={'key_id': 'audit-cli'},
            )
            (run_dir / 'report.json').write_text(json.dumps({'files': [{}]}), encoding='utf-8')
            env = os.environ.copy()
            env['CODEMOSAIC_AUDIT_KEY'] = 'cli-audit-key'
            result = subprocess.run(
                ['python', '-m', 'codemosaic', 'audit-runs', str(workspace), '--signing-key-env', 'CODEMOSAIC_AUDIT_KEY', '--output', str(report_path)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            self.assertIn('audited runs: 1', result.stdout)
            payload = json.loads(report_path.read_text(encoding='utf-8'))
            self.assertEqual(payload['summary']['verified_count'], 1)
            self.assertEqual(payload['runs'][0]['verification_status'], 'verified')
            self.assertEqual(payload['runs'][0]['signature_key_id'], 'audit-cli')

    def test_audit_run_mappings_require_signature_fails_for_unsigned_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            run_dir = workspace / '.codemosaic' / 'runs' / 'unsigned'
            run_dir.mkdir(parents=True)
            vault = MappingVault()
            vault.mask_identifier('deltaService')
            vault.save(run_dir / 'mapping.json')

            with self.assertRaises(ValueError):
                audit_run_mappings(workspace, require_signature=True)

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
