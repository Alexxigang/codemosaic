from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codemosaic.policy import MaskPolicy, load_policy
from codemosaic.workspace import resolve_workspace_mapping_policy


class PolicyLoaderTests(unittest.TestCase):
    def test_simple_yaml_subset_loads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / 'policy.yaml'
            policy_path.write_text(
                'paths:\n'
                '  include:\n'
                '    - "**/*.py"\n'
                'comments:\n'
                '  mode: placeholder\n'
                'mapping:\n'
                '  require_encryption: true\n'
                '  encryption_provider: prototype-v1\n'
                '  rules:\n'
                '    src/secret/**:\n'
                '      require_encryption: true\n',
                encoding='utf-8',
            )
            policy = load_policy(policy_path)
            self.assertEqual(policy.paths.include, ['**/*.py'])
            self.assertEqual(policy.comments.mode, 'placeholder')
            self.assertTrue(policy.mapping.require_encryption)
            self.assertEqual(policy.mapping.encryption_provider, 'prototype-v1')
            self.assertEqual(policy.mapping.rules[0].pattern, 'src/secret/**')

    def test_policy_loads_leakage_budget_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / 'policy.yaml'
            policy_path.write_text(
                'leakage:\n'
                '  max_total_score: 12\n'
                '  max_file_score: 4\n'
                '  rules:\n'
                '    src/secret/**:\n'
                '      max_total_score: 1\n'
                '      max_file_score: 0\n',
                encoding='utf-8',
            )
            policy = load_policy(policy_path)
            self.assertEqual(policy.leakage.max_total_score, 12)
            self.assertEqual(policy.leakage.max_file_score, 4)
            self.assertEqual(policy.leakage.rules[0].pattern, 'src/secret/**')
            self.assertEqual(policy.leakage.rules[0].max_total_score, 1)
            self.assertEqual(policy.leakage.rules[0].max_file_score, 0)

    def test_policy_resolves_mapping_enforcement_for_matched_files(self) -> None:
        policy = MaskPolicy.from_dict(
            {
                'mapping': {
                    'require_encryption': False,
                    'encryption_provider': 'prototype-v1',
                    'rules': {
                        'src/secret/**': {
                            'require_encryption': True,
                            'encryption_provider': 'prototype-v1',
                        }
                    },
                }
            }
        )
        resolved = policy.resolve_mapping_policy(['src/secret/app.py'])
        self.assertTrue(resolved.require_encryption)
        self.assertEqual(resolved.encryption_provider, 'prototype-v1')

    def test_policy_resolves_leakage_file_threshold_from_matching_rule(self) -> None:
        policy = MaskPolicy.from_dict(
            {
                'leakage': {
                    'max_file_score': 5,
                    'rules': {
                        'src/finance/**': {
                            'max_file_score': 0,
                        }
                    },
                }
            }
        )
        resolved = policy.resolve_leakage_file_policy('src/finance/app.py')
        self.assertEqual(resolved.max_file_score, 0)
        self.assertEqual(resolved.matched_pattern, 'src/finance/**')
        default_resolved = policy.resolve_leakage_file_policy('src/public/app.py')
        self.assertEqual(default_resolved.max_file_score, 5)
        self.assertIsNone(default_resolved.matched_pattern)

    def test_policy_detects_conflicting_provider_requirements(self) -> None:
        policy = MaskPolicy.from_dict(
            {
                'mapping': {
                    'rules': {
                        'src/secret/**': {
                            'require_encryption': True,
                            'encryption_provider': 'prototype-v1',
                        },
                        'src/payments/**': {
                            'require_encryption': True,
                            'encryption_provider': 'aesgcm-v1',
                        },
                    }
                }
            }
        )
        with self.assertRaises(ValueError):
            policy.resolve_mapping_policy(['src/secret/a.py', 'src/payments/b.py'])

    def test_workspace_policy_requires_passphrase_for_matching_files(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            workspace.mkdir()
            (workspace / 'src').mkdir()
            (workspace / 'src' / 'secret').mkdir()
            (workspace / 'src' / 'secret' / 'app.py').write_text('token = "abc"\n', encoding='utf-8')
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
                ['python', '-m', 'codemosaic', 'mask', str(workspace), '--policy', str(policy_path)],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn('policy requires encrypted mapping', result.stderr)

    def test_workspace_resolves_policy_provider_from_matching_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / 'repo'
            output_root = Path(temp_dir) / 'repo.masked'
            workspace.mkdir()
            (workspace / 'src').mkdir()
            (workspace / 'src' / 'secret').mkdir()
            (workspace / 'src' / 'secret' / 'app.py').write_text('token = "abc"\n', encoding='utf-8')
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
            resolved = resolve_workspace_mapping_policy(
                workspace,
                output_root,
                policy,
                encryption_requested=True,
                provider_override=None,
            )
            self.assertTrue(resolved.require_encryption)
            self.assertEqual(resolved.encryption_provider, 'prototype-v1')


if __name__ == '__main__':
    unittest.main()
