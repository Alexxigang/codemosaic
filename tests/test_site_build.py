from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


class SiteBuildTests(unittest.TestCase):
    def test_build_site_script_syncs_assets(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'site'
            subprocess.run(
                ['python', str(repo_root / 'scripts' / 'build_site.py'), '--output-root', str(output_root), '--clean-assets'],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertTrue((output_root / '.nojekyll').exists())
            self.assertTrue((output_root / 'assets' / 'workflow-overview.svg').exists())
            self.assertTrue((output_root / 'assets' / 'vscode-runs-view.svg').exists())
            self.assertTrue((output_root / 'assets' / 'safe-export-gate.svg').exists())


if __name__ == '__main__':
    unittest.main()
