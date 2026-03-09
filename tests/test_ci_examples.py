from __future__ import annotations

import unittest
from pathlib import Path


class CiExamplesTests(unittest.TestCase):
    def test_ci_governance_docs_and_example_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example = root / 'examples' / 'github-actions' / 'leakage-gate.yml'
        doc = root / 'docs' / 'ci-governance.md'
        self.assertTrue(example.exists())
        self.assertTrue(doc.exists())
        content = example.read_text(encoding='utf-8')
        self.assertIn('--fail-on-threshold', content)
        self.assertIn('presets/balanced-ai-gateway.yaml', content)


if __name__ == '__main__':
    unittest.main()
