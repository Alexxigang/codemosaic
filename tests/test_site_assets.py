from __future__ import annotations

import unittest
from pathlib import Path


class SiteAssetsTests(unittest.TestCase):
    def test_static_site_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / 'docs' / 'site' / 'index.html').exists())
        self.assertTrue((root / 'docs' / 'site' / 'style.css').exists())
        self.assertTrue((root / 'docs' / 'site' / '.nojekyll').exists())
        self.assertTrue((root / 'docs' / 'site' / '404.html').exists())
        self.assertTrue((root / 'docs' / 'site' / 'robots.txt').exists())
        self.assertTrue((root / 'docs' / 'site' / 'assets' / 'safe-export-gate.svg').exists())
        self.assertTrue((root / 'docs' / 'site' / 'assets' / 'social-card.svg').exists())

    def test_site_check_workflow_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = root / '.github' / 'workflows' / 'site-check.yml'
        self.assertTrue(workflow.exists())
        content = workflow.read_text(encoding='utf-8')
        self.assertIn('name: site-check', content)
        self.assertIn('python scripts/build_site.py --clean-assets', content)
        self.assertIn('python -m unittest tests.test_site_assets tests.test_site_build tests.test_release_files -v', content)
        release_template = root / '.github' / 'RELEASE_TEMPLATE.md'
        self.assertTrue(release_template.exists())

    def test_static_site_contains_social_meta_tags(self) -> None:
        root = Path(__file__).resolve().parents[1]
        content = (root / 'docs' / 'site' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('og:title', content)
        self.assertIn('twitter:card', content)
        self.assertIn('assets/social-card.svg', content)

    def test_static_site_exposes_bilingual_readme_links_and_no_mojibake_markers(self) -> None:
        root = Path(__file__).resolve().parents[1]
        content = (root / 'docs' / 'site' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('README.en.md', content)
        self.assertIn('README.zh-CN.md', content)
        self.assertIn('CodeMosaic - AI Code Privacy Gateway', content)
        self.assertNotIn('กช', content)
        self.assertNotIn('กค', content)
        self.assertNotIn('กฐ', content)
        self.assertNotIn('กฑ', content)


if __name__ == '__main__':
    unittest.main()
