import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from local_report import LocalReporter,template_report,make_report


class TemplateReportTests(unittest.TestCase):
    def test_only_observed_category_is_translated(self):
        for english,chinese in [('jacket','夹克'),('coat','外套'),('hoodie','连帽上衣'),
                                ('sweater','毛衣'),('t-shirt','T恤'),('shirt','衬衫')]:
            text=template_report('The visible person wears a '+english+'.','/capture/one/original.jpg')
            self.assertIn(chinese,text)
            self.assertIn('AI动漫拍照',text)
            self.assertNotIn('裙',text)

    def test_uncertain_observation_stays_neutral(self):
        for observation in ['Maybe a jacket.','No person visible.','A jacket or shirt.','Unknown.']:
            text=template_report(observation,'/one/original.jpg')
            self.assertNotIn('夹克',text)
            self.assertNotIn('衬衫',text)

    def test_variants_are_stable_and_do_not_invent_colors_or_pose(self):
        texts={template_report('A jacket.',f'/capture/{i}/original.jpg') for i in range(30)}
        self.assertEqual(len(texts),3)
        for text in texts:
            for claim in ['蓝色','白色','举起','微笑','男生','女生']:
                self.assertNotIn(claim,text)
        self.assertEqual(template_report('A jacket.','/one/original.jpg'),template_report('A jacket.','/one/original.jpg'))

    def test_bpu_template_never_starts_or_calls_text_model(self):
        starter=Mock();engine=LocalReporter(starter=starter,template_only=True)
        engine.wait_ready=Mock(side_effect=AssertionError('writer health requested'))
        engine.complete=Mock(side_effect=AssertionError('writer requested'))
        process=Mock();process.returncode=0
        process.communicate.return_value=(json.dumps({'text':'A blue jacket.','seconds':3,
                                                    'subject_visible':True,'model':'SmolVLM2-500M'}).encode(),b'')
        with patch('local_report.bpu_available',return_value=True),patch('local_report.helper_environment',return_value=None),patch('local_report.subprocess.Popen',return_value=process) as launch:
            text=engine.generate('/not-real/original.jpg')
        self.assertIn('夹克',text);starter.assert_not_called()
        engine.wait_ready.assert_not_called();engine.complete.assert_not_called()
        self.assertIn('/not-real/original.jpg',launch.call_args.args[0])

    def test_default_photo_flow_selects_template_reporter(self):
        engine=Mock();engine.generate.return_value='测试正文'
        with patch('local_report.LocalReporter',return_value=engine) as factory:
            self.assertEqual(make_report('/photo/original.jpg',True)['state'],'generated')
        factory.assert_called_once_with(template_only=True)
