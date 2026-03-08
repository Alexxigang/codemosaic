from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codemosaic.policy import MaskPolicy
from codemosaic.workspace import mask_workspace


class JstsWorkspaceTests(unittest.TestCase):
    def test_typescript_file_uses_dedicated_masker(self) -> None:
        source = (
            "// internal revenue flow\n"
            "export interface RevenueProfile { customerEmail: string }\n"
            "const revenueModel = async (apiSecret: string) => {\n"
            "  const baseUrl = \"https://internal.example.com\";\n"
            "  return `${baseUrl}/${apiSecret}`;\n"
            "};\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "repo"
            output_root = root / "repo.masked"
            source_root.mkdir()
            (source_root / "app.ts").write_text(source, encoding="utf-8")
            report = mask_workspace(source_root, output_root, MaskPolicy(), run_id="jsts")
            masked = (output_root / "app.ts").read_text(encoding="utf-8")
            self.assertNotIn("revenueModel", masked)
            self.assertNotIn("apiSecret", masked)
            self.assertNotIn("customerEmail", masked)
            self.assertNotIn("https://internal.example.com", masked)
            self.assertIn("STR_URL_0001", masked)
            self.assertIn("ID_0001", masked)
            self.assertIn("COMMENT_0001", masked)
            self.assertIn("${ID_", masked)
            self.assertIn("interface", masked)
            self.assertIn("export", masked)
            self.assertTrue(any(item.masker == "jsts" for item in report.files))


if __name__ == "__main__":
    unittest.main()
