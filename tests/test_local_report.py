import sys,unittest,io,json,tempfile
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from local_report import LocalReporter,make_report,clean_report,ENDPOINT,WRITER_ENDPOINT

class LocalReportTests(unittest.TestCase):
 def test_disabled_never_starts_or_calls_model(self):
  reporter=Mock()
  self.assertEqual(make_report('unused',False,reporter)['state'],'disabled')
  reporter.generate.assert_not_called()
 def test_timeout_uses_existing_copy(self):
  reporter=Mock();reporter.generate.side_effect=TimeoutError()
  result=make_report('photo',True,reporter)
  self.assertEqual(result['state'],'fallback');self.assertNotIn('text',result)
 def test_generation_is_loopback_only_and_sends_photo_and_prompt(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder:
   photo=Path(folder)/'photo.png';Image.new('RGB',(1000,600)).save(photo)
   starter=Mock();reporter=LocalReporter(starter=starter)
   health=io.BytesIO(b'{}');health.status=200
   writer_health=io.BytesIO(b'{}');writer_health.status=200
   text='照片中，体验者面对镜头留下动漫形象，AI拍报机将现场互动转化为科技节纪念，展现了人工智能创作的趣味。'
   result=io.BytesIO(json.dumps({'choices':[{'message':{'content':text}}]}).encode())
   caption=io.BytesIO(json.dumps({'choices':[{'message':{'content':'A person wearing a blue jacket sits near a window.'}}]}).encode())
   reporter.opener=Mock();reporter.opener.open.side_effect=[health,writer_health,caption,result]
   self.assertEqual(reporter.generate(photo),text)
   request=reporter.opener.open.call_args_list[2].args[0]
   self.assertEqual(request.full_url,ENDPOINT+'/v1/chat/completions')
   payload=json.loads(request.data)
   self.assertTrue(payload['messages'][0]['content'][0]['image_url']['url'].startswith('data:image/jpeg;base64,'))
   writer=reporter.opener.open.call_args_list[3].args[0]
   self.assertEqual(writer.full_url,WRITER_ENDPOINT+'/v1/chat/completions')
   self.assertIn('blue jacket',json.loads(writer.data)['messages'][1]['content'])
   starter.assert_called_once()
 def test_invalid_and_excessive_output(self):
  with self.assertRaises(ValueError):clean_report('English only')
  self.assertLessEqual(len(clean_report('体验者感受人工智能科技创作。'*20)),96)
 def test_short_grounded_description_gets_factual_project_closing(self):
  text=clean_report('一位穿着蓝色外套的人抬起手，动作清晰。')
  self.assertIn('蓝色外套',text);self.assertIn('科技节的专属纪念',text)
  self.assertIn('AI动漫拍照',clean_report('蓝衣体验者举起手臂。'))

if __name__=='__main__':unittest.main()
