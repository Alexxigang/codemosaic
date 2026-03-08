from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class CliSegmentationTests(unittest.TestCase):
    def test_plan_segments_writes_plan_file(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            output_plan = Path(temp_dir) / 'segment-plan.json'
            (workspace / 'src' / 'secret').mkdir(parents=True)
            (workspace / 'src' / 'public').mkdir(parents=True)
            (workspace / 'src' / 'secret' / 'secret.py').write_text('token = "abc"\n', encoding='utf-8')
            (workspace / 'src' / 'public' / 'public.py').write_text('value = 1\n', encoding='utf-8')
            policy_path = workspace / 'policy.yaml'
            policy_path.write_text(
                'mapping:\n'
                '  rules:\n'
                '    src/secret/**:\n'
                '      require_encryption: true\n'
                '      encryption_provider: prototype-v1\n',
                encoding='utf-8',
            )
            result = subprocess.run(
                ['python', '-m', 'codemosaic', 'plan-segments', str(workspace), '--policy', str(policy_path), '--output', str(output_plan)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn('segment count: 2', result.stdout)
            payload = json.loads(output_plan.read_text(encoding='utf-8'))
            self.assertEqual(payload['segment_count'], 2)

    def test_mask_segmented_generates_segmented_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            output_root = Path(temp_dir) / 'repo.masked.segmented'
            (workspace / 'src' / 'secret').mkdir(parents=True)
            (workspace / 'src' / 'public').mkdir(parents=True)
            (workspace / 'src' / 'secret' / 'secret.py').write_text('token = "abc"\n', encoding='utf-8')
            (workspace / 'src' / 'public' / 'public.py').write_text('value = 1\n', encoding='utf-8')
            policy_path = workspace / 'policy.yaml'
            policy_path.write_text(
                'mapping:\n'
                '  rules:\n'
                '    src/secret/**:\n'
                '      require_encryption: true\n'
                '      encryption_provider: prototype-v1\n',
                encoding='utf-8',
            )
            env = os.environ.copy()
            env['CODEMOSAIC_PASSPHRASE'] = 'secret-passphrase'
            result = subprocess.run(
                [
                    'python', '-m', 'codemosaic', 'mask-segmented', str(workspace), '--policy', str(policy_path), '--output', str(output_root), '--encrypt-mapping', '--passphrase-env', 'CODEMOSAIC_PASSPHRASE'
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            self.assertIn('segment count: 2', result.stdout)
            summary_file = output_root / 'segmented-mask-summary.json'
            self.assertTrue(summary_file.exists())
            payload = json.loads(summary_file.read_text(encoding='utf-8'))
            self.assertEqual(payload['segment_count'], 2)


if __name__ == '__main__':
    unittest.main()
