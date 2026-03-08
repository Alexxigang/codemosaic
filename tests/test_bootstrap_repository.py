from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


class BootstrapRepositoryTests(unittest.TestCase):
    def test_bootstrap_creates_release_files(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            subprocess.run(
                ['python', str(repo_root / 'scripts' / 'bootstrap_repository.py'), '--target-root', str(target)],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertTrue((target / '.gitattributes').exists())
            self.assertTrue((target / 'RELEASE_CHECKLIST.md').exists())
            self.assertTrue((target / 'CHANGELOG.md').exists())
            self.assertTrue((target / '.github' / 'RELEASE_TEMPLATE.md').exists())
            self.assertTrue((target / '.github' / 'ISSUE_TEMPLATE' / 'bug_report.md').exists())
            self.assertTrue((target / '.github' / 'ISSUE_TEMPLATE' / 'feature_request.md').exists())


if __name__ == '__main__':
    unittest.main()
