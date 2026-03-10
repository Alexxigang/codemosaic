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
            self.assertGreaterEqual(len(payload['registry_entries']), 2)
            actions = [item.get('action') for item in payload['audit_events']]
            self.assertIn('setup-workspace', actions)
            self.assertIn('mask', actions)


if __name__ == '__main__':
    unittest.main()
