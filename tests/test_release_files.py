from __future__ import annotations

import unittest
from pathlib import Path


class ReleaseFilesTests(unittest.TestCase):
    def test_release_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / 'RELEASE_CHECKLIST.md').exists())
        self.assertTrue((root / 'CHANGELOG.md').exists())

    def test_static_site_contains_release_ctas(self) -> None:
        root = Path(__file__).resolve().parents[1]
        content = (root / 'docs' / 'site' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('https://github.com/Alexxigang/codemosaic', content)
        self.assertIn('https://github.com/Alexxigang/codemosaic/releases', content)
        self.assertIn('RELEASE_CHECKLIST.md', content)


if __name__ == '__main__':
    unittest.main()
