from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'service'))
from local_report import LocalReporter, template_report, upper_clothing_observation
from report_category import available, person_box


class CategoryReportTests(unittest.TestCase):
    def test_missing_assets_do_not_activate_new_path(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(available(folder))

    def test_no_person_returns_no_crop(self):
        import numpy as np
        det = np.zeros((1, 85), dtype=np.float32)
        self.assertIsNone(person_box(det, 1920, 1080, 1/3,
                                    np.zeros((1, 2)), np.ones((1, 1))))

    def test_supported_categories_and_blouse_are_translated(self):
        for category, chinese in [('blouse', '衬衫'), ('cardigan', '开衫'),
                                  ('vest', '马甲'), ('dress', '连衣裙'),
                                  ('jumpsuit', '连体衣'), ('cape', '斗篷')]:
            self.assertIn(chinese, template_report('A '+category+'.', '/one/original.jpg', full_person=True))
            self.assertIsNone(upper_clothing_observation('Not a '+category+'.', full_person=True))
            self.assertIsNone(upper_clothing_observation('A '+category+' or shirt.', full_person=True))

    def test_structured_path_uses_original_and_never_calls_vlm(self):
        observation = {'subject_visible': True, 'category': 'jacket', 'seconds': .5,
                       'model': 'test fashion model', 'decoder': 'fixed similarity',
                       'source_box': [0, 0, 100, 200]}
        with patch('report_category.available', return_value=True), \
             patch('report_category.classify', return_value=observation) as classify, \
             patch('local_report.subprocess.Popen', side_effect=AssertionError('VLM called')):
            engine = LocalReporter(template_only=True)
            self.assertIn('夹克', engine.generate('/one/original.jpg'))
        classify.assert_called_once_with('/one/original.jpg')
        self.assertEqual(engine.backend, 'CPU fashion recognition + template')

    def test_person_guard_produces_neutral_report(self):
        observation = {'subject_visible': False, 'category': None, 'seconds': .3,
                       'model': 'test', 'decoder': 'fixed'}
        with patch('report_category.available', return_value=True), \
             patch('report_category.classify', return_value=observation):
            text = LocalReporter(template_only=True).generate('/empty/original.jpg')
        for claim in ['身穿', '身着', '夹克', '连衣裙']:
            self.assertNotIn(claim, text)
