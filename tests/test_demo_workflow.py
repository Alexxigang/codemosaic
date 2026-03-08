from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class DemoWorkflowTests(unittest.TestCase):
    def test_demo_workflow_generates_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'demo-output'
            subprocess.run(
                [
                    'python',
                    str(repo_root / 'scripts' / 'run_demo_workflow.py'),
                    '--output-root',
                    str(output_root),
                    '--encrypt-mapping',
                    '--clean',
                ],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            summary_file = output_root / 'demo-summary.json'
            markdown_file = output_root / 'demo-summary.md'
            self.assertTrue(summary_file.exists())
            self.assertTrue(markdown_file.exists())
            payload = json.loads(summary_file.read_text(encoding='utf-8'))
            self.assertTrue(str(payload['mapping_file']).endswith('mapping.enc.json'))
            self.assertTrue(Path(payload['bundle_file']).exists())
            self.assertTrue(Path(payload['masked_root']).exists())
            self.assertTrue(Path(payload['leakage_report_file']).exists())
            self.assertEqual(payload['safe_export']['status'], 'blocked')
            self.assertTrue(payload['safe_export']['messages'])


if __name__ == '__main__':
    unittest.main()
