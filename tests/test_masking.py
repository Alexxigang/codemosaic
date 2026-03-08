from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codemosaic.policy import MaskPolicy
from codemosaic.workspace import mask_workspace


class MaskWorkspaceTests(unittest.TestCase):
    def test_python_file_is_masked(self) -> None:
        source = (
            "# quarterly revenue plan\n"
            "API_SECRET = \"super-secret-token\"\n\n"
            "def compute_revenue(user_email):\n"
            "    return API_SECRET, user_email\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "repo"
            output_root = root / "repo.masked"
            source_root.mkdir()
            (source_root / "app.py").write_text(source, encoding="utf-8")
            report = mask_workspace(source_root, output_root, MaskPolicy(), run_id="testrun")
            masked = (output_root / "app.py").read_text(encoding="utf-8")
            self.assertNotIn("compute_revenue", masked)
            self.assertNotIn("user_email", masked)
            self.assertNotIn("super-secret-token", masked)
            self.assertNotIn("quarterly revenue plan", masked)
            self.assertIn("ID_0001", masked)
            self.assertIn("STR_SECRET_0001", masked)
            self.assertIn("COMMENT_0001", masked)
            self.assertTrue(Path(report.mapping_file).exists())


if __name__ == "__main__":
    unittest.main()
