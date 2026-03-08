from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class ReleaseAssetsTests(unittest.TestCase):
    def test_release_asset_generator_creates_manifest_and_checksums(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'release-assets'
            subprocess.run(
                [
                    'python',
                    str(repo_root / 'scripts' / 'generate_release_assets.py'),
                    '--output-root',
                    str(output_root),
                    '--encrypt-mapping',
                    '--clean',
                ],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            manifest_path = output_root / 'release-manifest.json'
            checksums_path = output_root / 'SHA256SUMS.txt'
            summary_path = output_root / 'release-summary.md'
            self.assertTrue(manifest_path.exists())
            self.assertTrue(checksums_path.exists())
            self.assertTrue(summary_path.exists())
            payload = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertIn('vsix_file', payload)
            self.assertIn('checksums', payload)
            self.assertTrue(Path(payload['vsix_file']).exists())
            self.assertIn('safe_export', payload['demo_summary'])
            self.assertEqual(payload['demo_summary']['safe_export']['status'], 'blocked')
            self.assertIn('demo_leakage_report', payload['assets'])


if __name__ == '__main__':
    unittest.main()
