from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


class CliProvidersTests(unittest.TestCase):
    def test_list_providers_includes_default_provider(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['python', '-m', 'codemosaic', 'list-providers'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn('prototype-v1', result.stdout)
        self.assertIn('built-in', result.stdout)


if __name__ == '__main__':
    unittest.main()
