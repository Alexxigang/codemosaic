from __future__ import annotations

import unittest
from pathlib import Path


class SiteAssetsTests(unittest.TestCase):
    def test_static_site_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / 'docs' / 'site' / 'index.html').exists())
        self.assertTrue((root / 'docs' / 'site' / 'style.css').exists())
        self.assertTrue((root / 'docs' / 'site' / '.nojekyll').exists())
        self.assertTrue((root / 'docs' / 'site' / 'assets' / 'safe-export-gate.svg').exists())

    def test_pages_workflow_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = root / '.github' / 'workflows' / 'deploy-pages.yml'
        self.assertTrue(workflow.exists())
        content = workflow.read_text(encoding='utf-8')
        self.assertIn('actions/deploy-pages@v4', content)
        self.assertIn('path: docs/site', content)
        self.assertIn('python scripts/build_site.py --clean-assets', content)


if __name__ == '__main__':
    unittest.main()
