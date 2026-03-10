from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class SecureOnboardingDemoTests(unittest.TestCase):
    def test_secure_onboarding_demo_generates_expected_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'secure-onboarding-demo'
            subprocess.run(
                [
                    'python',
                    str(repo_root / 'scripts' / 'run_secure_onboarding_demo.py'),
                    '--output-root',
                    str(output_root),
                    '--clean',
                ],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            summary_file = output_root / 'secure-onboarding-summary.json'
            markdown_file = output_root / 'secure-onboarding-summary.md'
            self.assertTrue(summary_file.exists())
            self.assertTrue(markdown_file.exists())
            payload = json.loads(summary_file.read_text(encoding='utf-8'))
            self.assertTrue(Path(payload['policy_path']).exists())
            self.assertTrue(Path(payload['registry_path']).exists())
            self.assertTrue(Path(payload['mapping_file']).exists())
            self.assertTrue(str(payload['mapping_file']).endswith('mapping.enc.json'))
            self.assertTrue(Path(payload['leakage_report_file']).exists())
            self.assertTrue(Path(payload['run_audit_file']).exists())
            self.assertFalse(payload['before_state']['policy_ready'])
            self.assertTrue(payload['after_state']['policy_ready'])
            self.assertGreaterEqual(payload['after_state']['managed_key_file_count'], 2)
            self.assertGreaterEqual(len(payload['registry_entries']), 2)
            self.assertEqual(payload['run_audit_summary']['verified_count'], 1)
            self.assertIn('verified: yes', payload['verify_mapping_output'])
            actions = [item.get('action') for item in payload['audit_events']]
            self.assertIn('setup-workspace', actions)
            self.assertIn('mask', actions)
            self.assertIn('verify-mapping', actions)
            self.assertIn('audit-runs', actions)


if __name__ == '__main__':
    unittest.main()
