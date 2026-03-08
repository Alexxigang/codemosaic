from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codemosaic.leakage import analyze_masked_file, evaluate_leakage_budget, leakage_report
from codemosaic.policy import MaskPolicy


class LeakageReportTests(unittest.TestCase):
    def test_analyze_masked_file_flags_semantic_residue(self) -> None:
        analysis = analyze_masked_file(
            'src/pricing_engine.py',
            'def merchantSettlement(ID_0001):\n'
            '    // internal payout rule\n'
            '    return "merchant_tier_gold"\n',
        )
        self.assertGreater(analysis['score'], 0)
        self.assertIn('pricing', [item.lower() for item in analysis['examples']['path_terms']])
        self.assertIn('merchantSettlement', analysis['examples']['identifiers'])
        self.assertIn('merchant_tier_gold', analysis['examples']['strings'])
        self.assertEqual(analysis['risk'], 'high')

    def test_leakage_report_outputs_ranked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / 'masked'
            (source_root / 'src').mkdir(parents=True)
            (source_root / 'src' / 'pricing_engine.py').write_text(
                'def merchantSettlement(ID_0001):\n'
                '    return "merchant_tier_gold"\n',
                encoding='utf-8',
            )
            (source_root / 'src' / 'safe.py').write_text(
                'def run(ID_0001):\n'
                '    return "STR_GENERIC_0001"\n',
                encoding='utf-8',
            )
            report = leakage_report(source_root, MaskPolicy())
            self.assertEqual(report['summary']['scanned_files'], 2)
            self.assertEqual(report['files'][0]['path'], 'src/pricing_engine.py')
            self.assertIn('src/pricing_engine.py', report['summary']['highest_risk_files'])

    def test_evaluate_leakage_budget_detects_global_file_and_rule_violations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / 'masked'
            (source_root / 'src' / 'pricing').mkdir(parents=True)
            (source_root / 'src' / 'pricing' / 'engine.py').write_text(
                'def merchantSettlement(ID_0001):\n'
                '    // internal payout rule\n'
                '    return "merchant_tier_gold"\n',
                encoding='utf-8',
            )
            policy = MaskPolicy.from_dict(
                {
                    'leakage': {
                        'max_total_score': 3,
                        'max_file_score': 2,
                        'rules': {
                            'src/pricing/**': {
                                'max_total_score': 4,
                                'max_file_score': 1,
                            }
                        },
                    }
                }
            )
            report = leakage_report(source_root, policy)
            budget = evaluate_leakage_budget(report, policy)
            self.assertIsNotNone(budget)
            assert budget is not None
            self.assertFalse(budget['passed'])
            violation_types = {item['type'] for item in budget['violations']}
            self.assertIn('global_total', violation_types)
            self.assertIn('file_score', violation_types)
            self.assertIn('rule_total', violation_types)

    def test_evaluate_leakage_budget_returns_none_without_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / 'masked'
            (source_root / 'src').mkdir(parents=True)
            (source_root / 'src' / 'safe.py').write_text(
                'def run(ID_0001):\n'
                '    return "STR_GENERIC_0001"\n',
                encoding='utf-8',
            )
            report = leakage_report(source_root, MaskPolicy())
            self.assertIsNone(evaluate_leakage_budget(report, MaskPolicy()))


if __name__ == '__main__':
    unittest.main()
