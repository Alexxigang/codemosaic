from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class ReleasePageTests(unittest.TestCase):
    def test_release_asset_generator_creates_release_page_and_screenshot_manifest(self) -> None:
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
            release_page = output_root / 'release-page.md'
            screenshot_manifest = output_root / 'screenshot-manifest.json'
            self.assertTrue(release_page.exists())
            self.assertTrue(screenshot_manifest.exists())
            content = release_page.read_text(encoding='utf-8')
            self.assertIn('# CodeMosaic Release Draft', content)
            payload = json.loads(screenshot_manifest.read_text(encoding='utf-8'))
            self.assertIn('recommended_assets', payload)
            self.assertGreaterEqual(len(payload['recommended_assets']), 2)


if __name__ == '__main__':
    unittest.main()
