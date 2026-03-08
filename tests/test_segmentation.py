from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codemosaic.policy import MaskPolicy
from codemosaic.segmentation import mask_segmented_workspace, plan_mask_segments


class SegmentationTests(unittest.TestCase):
    def test_plan_mask_segments_groups_by_mapping_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / 'repo'
            output_root = root / 'repo.masked.segmented'
            (source_root / 'src' / 'secret').mkdir(parents=True)
            (source_root / 'src' / 'public').mkdir(parents=True)
            (source_root / 'src' / 'secret' / 'secret.py').write_text('token = "abc"\n', encoding='utf-8')
            (source_root / 'src' / 'public' / 'public.py').write_text('value = 1\n', encoding='utf-8')
            policy = MaskPolicy.from_dict(
                {
                    'mapping': {
                        'rules': {
                            'src/secret/**': {
                                'require_encryption': True,
                                'encryption_provider': 'prototype-v1',
                            }
                        }
                    }
                }
            )
            segments = plan_mask_segments(source_root, output_root, policy)
            self.assertEqual(len(segments), 2)
            self.assertTrue(any(segment.effective_mapping.require_encryption for segment in segments))
            self.assertTrue(any(not segment.effective_mapping.require_encryption for segment in segments))

    def test_mask_segmented_workspace_writes_summary_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / 'repo'
            output_root = root / 'repo.masked.segmented'
            (source_root / 'src' / 'secret').mkdir(parents=True)
            (source_root / 'src' / 'public').mkdir(parents=True)
            (source_root / 'src' / 'secret' / 'secret.py').write_text('token = "abc"\n', encoding='utf-8')
            (source_root / 'src' / 'public' / 'public.py').write_text('value = 1\n', encoding='utf-8')
            policy = MaskPolicy.from_dict(
                {
                    'mapping': {
                        'rules': {
                            'src/secret/**': {
                                'require_encryption': True,
                                'encryption_provider': 'prototype-v1',
                            }
                        }
                    }
                }
            )
            result = mask_segmented_workspace(
                source_root,
                output_root,
                policy,
                run_id_prefix='seg',
                mapping_passphrase='secret-passphrase',
            )
            self.assertEqual(len(result.segments), 2)
            self.assertEqual(len(result.reports), 2)
            self.assertTrue(all(Path(report.mapping_file).exists() for report in result.reports))
            self.assertTrue(all(Path(report.output_root).exists() for report in result.reports))


if __name__ == '__main__':
    unittest.main()
