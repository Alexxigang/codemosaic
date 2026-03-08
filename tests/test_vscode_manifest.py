from __future__ import annotations

import json
import unittest
from pathlib import Path


class VscodeManifestTests(unittest.TestCase):
    def test_manifest_exposes_plan_segments_command(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        commands = {item['command'] for item in payload['contributes']['commands']}
        self.assertIn('codemosaic.planSegments', commands)
        activation_events = set(payload['activationEvents'])
        self.assertIn('onCommand:codemosaic.planSegments', activation_events)

    def test_manifest_exposes_leakage_report_command(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        commands = {item['command'] for item in payload['contributes']['commands']}
        self.assertIn('codemosaic.leakageReport', commands)
        activation_events = set(payload['activationEvents'])
        self.assertIn('onCommand:codemosaic.leakageReport', activation_events)


    def test_manifest_exposes_safe_bundle_command(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        commands = {item['command'] for item in payload['contributes']['commands']}
        self.assertIn('codemosaic.safeBundleMaskedWorkspace', commands)
        activation_events = set(payload['activationEvents'])
        self.assertIn('onCommand:codemosaic.safeBundleMaskedWorkspace', activation_events)

    def test_manifest_exposes_mask_segmented_workspace_command(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        commands = {item['command'] for item in payload['contributes']['commands']}
        self.assertIn('codemosaic.maskSegmentedWorkspace', commands)
        activation_events = set(payload['activationEvents'])
        self.assertIn('onCommand:codemosaic.maskSegmentedWorkspace', activation_events)

    def test_manifest_exposes_rekey_mapping_command(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        commands = {item['command'] for item in payload['contributes']['commands']}
        self.assertIn('codemosaic.rekeyMapping', commands)
        activation_events = set(payload['activationEvents'])
        self.assertIn('onCommand:codemosaic.rekeyMapping', activation_events)

    def test_manifest_exposes_rekey_recent_runs_command(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        commands = {item['command'] for item in payload['contributes']['commands']}
        self.assertIn('codemosaic.rekeyRecentRuns', commands)
        activation_events = set(payload['activationEvents'])
        self.assertIn('onCommand:codemosaic.rekeyRecentRuns', activation_events)

    def test_manifest_exposes_provider_listing_command(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        commands = {item['command'] for item in payload['contributes']['commands']}
        self.assertIn('codemosaic.showEncryptionProviders', commands)
        properties = payload['contributes']['configuration']['properties']
        self.assertIn('codemosaic.encryptionProvider', properties)

    def test_manifest_adds_mapping_context_menu(self) -> None:
        package_json = Path(__file__).resolve().parents[1] / 'extensions' / 'vscode' / 'package.json'
        payload = json.loads(package_json.read_text(encoding='utf-8'))
        menu_items = payload['contributes']['menus']['view/item/context']
        self.assertTrue(
            any(
                item['command'] == 'codemosaic.rekeyMapping'
                and 'codemosaicMappingArtifact' in item['when']
                for item in menu_items
            )
        )


if __name__ == '__main__':
    unittest.main()
