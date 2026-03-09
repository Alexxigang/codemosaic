from __future__ import annotations

import unittest
from pathlib import Path

from codemosaic.policy import load_policy


class PolicyPresetsTests(unittest.TestCase):
    def test_policy_presets_exist_and_load(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in [
            'strict-ai-gateway.yaml',
            'balanced-ai-gateway.yaml',
            'public-sdk-ai-gateway.yaml',
        ]:
            path = root / 'presets' / name
            self.assertTrue(path.exists())
            policy = load_policy(path)
            self.assertIsNotNone(policy.leakage)

    def test_strict_preset_requires_encrypted_mapping(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = load_policy(root / 'presets' / 'strict-ai-gateway.yaml')
        self.assertTrue(policy.mapping.require_encryption)


if __name__ == '__main__':
    unittest.main()
