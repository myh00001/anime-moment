import sys,unittest,io,json,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from local_report import LocalReporter,make_report,clean_report,ENDPOINT,WRITER_ENDPOINT,PROMPT,validate_clothing,upper_clothing_observation

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
  self.assertIn('蓝色外套',clean_report('画面观察：蓝色外套。'))

 def test_prompt_includes_verified_context_and_separates_it_from_observation(self):
  for phrase in ['北京市第六十五中学2026年校园科技节','做中学科学','实践促创新','漫像时刻','不代表图片里一定发生','身份','不得猜测']:self.assertIn(phrase,PROMPT)

 def test_bpu_path_uses_original_file_and_only_calls_cpu_writer(self):
  reporter=LocalReporter(starter=Mock());health=io.BytesIO(b'{}');health.status=200
  text='蓝色外套的体验者面向镜头。AI动漫拍照留下科技节纪念。'
  writer=io.BytesIO(json.dumps({'choices':[{'message':{'content':text}}]}).encode())
  reporter.opener=Mock();reporter.opener.open.side_effect=[health,writer]
  process=Mock();process.returncode=0
  process.communicate.return_value=(json.dumps({'text':'A person in a blue jacket faces the camera.','seconds':3.2}).encode(),b'')
  with patch('local_report.bpu_available',return_value=True),patch('local_report.subprocess.Popen',return_value=process) as launch:
   self.assertEqual(reporter.generate('/local/capture/original.jpg'),text)
  self.assertIn('/local/capture/original.jpg',launch.call_args.args[0])
  self.assertEqual(reporter.opener.open.call_count,2)
  self.assertEqual(reporter.backend,'S100 BPU vision + CPU text')
  self.assertEqual(reporter.vision_seconds,3.2)
  self.assertIn('blue jacket',json.loads(reporter.opener.open.call_args.args[0].data)['messages'][1]['content'])

 def test_writer_cannot_turn_jacket_into_dress(self):
  with self.assertRaises(ValueError):validate_clothing('体验者身穿连衣裙。','A blue jacket with a black collar.')
  self.assertEqual(validate_clothing('体验者身穿夹克。','A blue jacket.'),'体验者身穿夹克。')
  self.assertEqual(validate_clothing('体验者身穿连衣裙。','A person wearing a dress.'),'体验者身穿连衣裙。')
 def test_no_reliable_subject_never_describes_clothing_rack_as_person(self):
  reporter=LocalReporter(starter=Mock());health=io.BytesIO(b'{}');health.status=200
  reporter.opener=Mock();reporter.opener.open.return_value=health
  process=Mock();process.returncode=0
  process.communicate.return_value=(json.dumps({'text':'No reliable subject.','seconds':0,'subject_visible':False,'model':'SmolVLM2-500M'}).encode(),b'')
  with patch('local_report.bpu_available',return_value=True),patch('local_report.subprocess.Popen',return_value=process):text=reporter.generate('/local/original.jpg')
  self.assertIn('科技节',text);self.assertNotIn('人',text);self.assertNotIn('裙',text)
  self.assertEqual(reporter.opener.open.call_count,1)

 def test_upper_body_observation_does_not_claim_unseen_pants_or_dress(self):
  self.assertEqual(upper_clothing_observation('black jacket and black pants.'),'The visible person wears a jacket.')
  self.assertIsNone(upper_clothing_observation('A blue dress.'))
  with self.assertRaises(ValueError):validate_clothing('黑色外套和黑色裤子。','A black jacket and pants.')

if __name__=='__main__':unittest.main()
