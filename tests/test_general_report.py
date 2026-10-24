import sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from local_report import make_report,GeneralVLMReporter
class GeneralRouting(unittest.TestCase):
 def test_default_is_generative_and_keeps_original_path(self):
  with patch('local_report.GeneralVLMReporter') as cls,patch('report_category.classify') as classify:
   engine=cls.return_value;engine.generate.return_value='人物面向镜头，AI影像为科技节留下现场纪念。'
   engine.backend='InternVL3 general VLM: BPU vision + CPU generation'
   result=make_report('/capture/original.jpg',True)
   engine.generate.assert_called_once_with('/capture/original.jpg');classify.assert_not_called()
   self.assertEqual(result['state'],'generated');self.assertIn('general VLM',result['backend'])
 def test_model_failure_never_falls_back_to_clothing_classifier(self):
  with patch.object(GeneralVLMReporter,'generate',side_effect=RuntimeError),patch('report_category.classify') as classify:
   result=make_report('/capture/original.jpg',True)
   self.assertEqual(result['state'],'fallback');classify.assert_not_called()
if __name__=='__main__':unittest.main()
