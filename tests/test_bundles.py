from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codemosaic.bundles import build_markdown_bundle


class BundleTests(unittest.TestCase):
    def test_bundle_contains_tree_and_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "masked"
            source_root.mkdir()
            (source_root / "app.py").write_text('print("STR_GENERIC_0001")\n', encoding="utf-8")
            (source_root / "README.md").write_text('# Demo\n', encoding="utf-8")
            output_file = root / "bundle.md"
            build_markdown_bundle(source_root, output_file, max_files=10, max_chars_per_file=200)
            content = output_file.read_text(encoding="utf-8")
            self.assertIn("# AI Context Bundle", content)
            self.assertIn("`app.py`", content)
            self.assertIn("STR_GENERIC_0001", content)
            self.assertIn("## Tree", content)


if __name__ == "__main__":
    unittest.main()
