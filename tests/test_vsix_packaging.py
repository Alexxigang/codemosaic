from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


class VsixPackagingTests(unittest.TestCase):
    def test_packaging_script_builds_vsix(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            subprocess.run(
                [
                    'python',
                    str(repo_root / 'scripts' / 'package_vscode_extension.py'),
                    '--output-dir',
                    str(output_dir),
                    '--overwrite',
                ],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            vsix_files = list(output_dir.glob('*.vsix'))
            self.assertEqual(len(vsix_files), 1)
            with ZipFile(vsix_files[0]) as archive:
                names = set(archive.namelist())
                self.assertIn('extension/package.json', names)
                self.assertIn('extension/extension.js', names)
                self.assertIn('extension/README.md', names)
                self.assertIn('extension/LICENSE', names)
                self.assertIn('extension.vsixmanifest', names)
                self.assertIn('[Content_Types].xml', names)


if __name__ == '__main__':
    unittest.main()
