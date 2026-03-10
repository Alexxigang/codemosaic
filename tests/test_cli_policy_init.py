from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


class CliPolicyInitTests(unittest.TestCase):
    def test_list_policy_presets_reports_built_in_profiles(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['python', '-m', 'codemosaic', 'list-policy-presets', '--verbose'],
            check=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        self.assertIn('available presets: 3', result.stdout)
        self.assertIn('strict-ai-gateway', result.stdout)
        self.assertIn('balanced-ai-gateway', result.stdout)
        self.assertIn('public-sdk-ai-gateway', result.stdout)
        self.assertIn('recommended for:', result.stdout)

    def test_init_policy_copies_selected_preset(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        expected = (repo_root / 'presets' / 'strict-ai-gateway.yaml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'configs' / 'team-policy.yaml'
            result = subprocess.run(
                ['python', '-m', 'codemosaic', 'init-policy', '--preset', 'strict-ai-gateway', '--output', str(output_path)],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(output_path.read_text(encoding='utf-8'), expected)
            self.assertIn('created policy:', result.stdout)
            self.assertIn('preset: strict-ai-gateway', result.stdout)

    def test_init_policy_requires_force_for_existing_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'policy.codemosaic.yaml'
            output_path.write_text('custom: true\n', encoding='utf-8')
            result = subprocess.run(
                ['python', '-m', 'codemosaic', 'init-policy', '--output', str(output_path)],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn('output already exists:', result.stderr)
            self.assertEqual(output_path.read_text(encoding='utf-8'), 'custom: true\n')

    def test_init_policy_force_overwrites_existing_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        expected = (repo_root / 'presets' / 'balanced-ai-gateway.yaml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'policy.codemosaic.yaml'
            output_path.write_text('custom: true\n', encoding='utf-8')
            subprocess.run(
                ['python', '-m', 'codemosaic', 'init-policy', '--output', str(output_path), '--force'],
                check=True,
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(output_path.read_text(encoding='utf-8'), expected)


if __name__ == '__main__':
    unittest.main()
