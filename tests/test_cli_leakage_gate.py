from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


class CliLeakageGateTests(unittest.TestCase):
    def test_bundle_blocks_export_when_leakage_budget_fails(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path(temp_dir) / 'masked'
            bundle_file = Path(temp_dir) / 'ai-bundle.md'
            policy_path = Path(temp_dir) / 'policy.yaml'
            (source_root / 'src' / 'pricing').mkdir(parents=True)
            (source_root / 'src' / 'pricing' / 'engine.py').write_text(
                'def merchantSettlement(ID_0001):\n'
                '    // internal payout rule\n'
                '    return "merchant_tier_gold"\n',
                encoding='utf-8',
            )
            policy_path.write_text(
                'leakage:\n'
                '  max_total_score: 0\n'
                '  max_file_score: 0\n',
                encoding='utf-8',
            )
            result = subprocess.run(
                [
                    'python',
                    '-m',
                    'codemosaic',
                    'bundle',
                    str(source_root),
                    '--policy',
                    str(policy_path),
                    '--output',
                    str(bundle_file),
                    '--fail-on-threshold',
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 3)
            self.assertIn('bundle blocked by leakage budget', result.stdout)
            self.assertFalse(bundle_file.exists())


if __name__ == '__main__':
    unittest.main()
