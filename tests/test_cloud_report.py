import base64
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock,patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
import report_cloud
from report_router import generate_report
from report_secrets import load_key,save_key
from festival_settings import load_options,save_options


class Transport:
    def __init__(self,response=None,error=None):self.requests=[];self.response=response;self.error=error
    def open(self,request,timeout):
        self.requests.append(request)
        if self.error:raise self.error
        return io.BytesIO(json.dumps(self.response).encode())


def completion(text='画面中的人物面对镜头，举起双手。AI影像体验为科技节留下纪念。'):
    return {'choices':[{'finish_reason':'stop','message':{'content':text}}]}


class CloudReportTests(unittest.TestCase):
    def test_key_is_separate_private_and_never_copied_into_options(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_key(root,'unit-test-key')
            options=save_options(root/'settings.json',{'ai_report':True,'report_provider':'deepseek'})
            self.assertEqual(load_key(root),'unit-test-key')
            self.assertEqual(load_options(root/'settings.json')['report_provider'],'deepseek')
            self.assertNotIn('unit-test-key',(root/'settings.json').read_text())
            self.assertNotIn('api_key',str(options))
            if os.name!='nt':self.assertEqual(stat.S_IMODE((root/'report-secrets.json').stat().st_mode),0o600)
            with self.assertRaises(ValueError):save_key(root,'bad\nheader')
            self.assertEqual(load_key(root),'unit-test-key')
            save_key(root,'');self.assertEqual(load_key(root),'')

    def test_old_options_stay_local_and_unknown_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';save_options(path,{'ai_report':True})
            self.assertEqual(load_options(path).get('report_provider','local'),'local')
            with self.assertRaises(ValueError):save_options(path,{'report_provider':'other'})

    def test_original_pixels_are_sent_directly_to_exact_flash_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_key(root,'unit-test-key')
            Image.new('RGB',(160,90),'blue').save(root/'original.jpg')
            Image.new('RGB',(160,90),'red').save(root/'photo.jpg')
            transport=Transport(completion())
            result=report_cloud.make_cloud_report(root/'original.jpg',root,transport)
            self.assertEqual(result['state'],'generated');self.assertEqual(result['model'],'deepseek-flash')
            self.assertNotIn('unit-test-key',json.dumps(result));self.assertEqual(len(transport.requests),1)
            req=transport.requests[0];payload=json.loads(req.data)
            self.assertEqual(req.full_url,'https://api.deepseek.com/chat/completions')
            self.assertEqual(req.get_header('Authorization'),'Bearer unit-test-key')
            self.assertEqual(payload['model'],'deepseek-flash')
            self.assertEqual(payload['thinking'],{'type':'disabled'})
            picture=payload['messages'][1]['content'][1]['image_url']
            image=Image.open(io.BytesIO(base64.b64decode(picture['url'].split(',')[1])))
            red,green,blue=image.getpixel((50,40));self.assertGreater(blue,240);self.assertLess(red,15)
            self.assertEqual(image.size,(160,90));self.assertEqual(picture['detail'],'high')

    def test_disabled_or_local_selection_never_invokes_cloud(self):
        local=Mock(return_value={'state':'disabled'})
        with patch('report_cloud.make_cloud_report') as cloud:
            generate_report('original.jpg',{'ai_report':False,'report_provider':'deepseek'},'.',local)
            generate_report('original.jpg',{'ai_report':True,'report_provider':'local'},'.',local)
            cloud.assert_not_called();self.assertEqual(local.call_count,2)

    def test_cloud_selection_never_starts_local_model(self):
        local=Mock(side_effect=AssertionError('Local model started'))
        with patch('report_cloud.make_cloud_report',return_value={'state':'generated'}) as cloud:
            generate_report('original.jpg',{'ai_report':True,'report_provider':'deepseek'},'.',local)
            cloud.assert_called_once_with('original.jpg','.');local.assert_not_called()

    def test_missing_key_does_not_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            transport=Transport(completion());result=report_cloud.make_cloud_report('absent.jpg',folder,transport)
            self.assertEqual(result['reason'],'MissingAPIKey');self.assertEqual(transport.requests,[])

    def test_errors_are_redacted_and_not_retried(self):
        for error in [urllib.error.HTTPError(report_cloud.ENDPOINT,401,'unit-test-key',{},None),TimeoutError(),
                      urllib.error.URLError('unit-test-key')]:
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);save_key(root,'unit-test-key');Image.new('RGB',(10,10)).save(root/'original.jpg')
                transport=Transport(error=error)
                result=report_cloud.make_cloud_report(root/'original.jpg',root,transport)
                self.assertEqual(result['state'],'fallback');self.assertNotIn('unit-test-key',json.dumps(result))
                self.assertEqual(len(transport.requests),1)

    def test_connection_check_does_not_send_image(self):
        transport=Transport(completion('连接成功'))
        self.assertIn('连接成功',report_cloud.test_connection('unit-test-key',transport))
        payload=json.loads(transport.requests[0].data)
        self.assertIsInstance(payload['messages'][0]['content'],str)
        self.assertNotIn('image_url',json.dumps(payload))

    def test_empty_or_truncated_response_is_not_published(self):
        for result in [completion(''),{'choices':[]},dict(choices=[{'finish_reason':'length','message':{'content':'未完成'}}])]:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);save_key(root,'unit-test-key');Image.new('RGB',(10,10)).save(root/'original.jpg')
                report=report_cloud.make_cloud_report(root/'original.jpg',root,Transport(result))
                self.assertEqual(report['state'],'fallback')


if __name__=='__main__':unittest.main()
