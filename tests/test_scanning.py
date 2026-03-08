from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codemosaic.scanning import scan_workspace
from codemosaic.policy import MaskPolicy


class ScanWorkspaceTests(unittest.TestCase):
    def test_scan_finds_common_sensitive_markers(self) -> None:
        source = (
            "# TODO internal migration\n"
            "API_KEY = \"sk-live-123\"\n"
            "EMAIL = \"dev@internal.local\"\n"
            "URL = \"https://api.internal.local/v1\"\n"
            "PHONE = \"+86 13800138000\"\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "repo"
            source_root.mkdir()
            (source_root / "app.py").write_text(source, encoding="utf-8")
            report = scan_workspace(source_root, MaskPolicy())
            counts = report["summary"]["finding_counts"]
            self.assertGreaterEqual(counts["secrets"], 1)
            self.assertGreaterEqual(counts["emails"], 1)
            self.assertGreaterEqual(counts["urls"], 1)
            self.assertGreaterEqual(counts["phones"], 1)
            self.assertGreaterEqual(counts["internal_hosts"], 1)
            self.assertGreaterEqual(counts["comment_hints"], 1)


if __name__ == "__main__":
    unittest.main()
