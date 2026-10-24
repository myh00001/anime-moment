import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from report_general_vlm import VisionRuntime


class ResidentRuntimeTests(unittest.TestCase):
    def test_model_reused_but_each_original_is_sent_without_prompt_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,color in [('one','red'),('two','blue')]:
                Image.new('RGB',(80,60),color).save(root/(name+'.jpg'))
            process=Mock();process.poll.return_value=None
            health=io.BytesIO(b'{}');health.status=200
            outputs=[io.BytesIO(json.dumps({'choices':[{'message':{'content':text}}]}).encode())
                     for text in ['人物面对镜头。','房间内有一张桌子。']]
            with patch('report_general_vlm.subprocess.Popen',return_value=process) as launch:
                runtime=VisionRuntime(root)
                runtime.opener=Mock();runtime.opener.open.side_effect=[health,*outputs]
                try:
                    one=runtime.generate(root/'one.jpg')
                    two=runtime.generate(root/'two.jpg')
                    self.assertNotEqual(one['text'],two['text'])
                    launch.assert_called_once()
                    requests=[json.loads(call.args[0].data) for call in runtime.opener.open.call_args_list[1:]]
                    self.assertTrue(all(item['cache_prompt'] is False for item in requests))
                    pictures=[item['messages'][1]['content'][0]['image_url']['url'] for item in requests]
                    self.assertNotEqual(*pictures)
                finally:runtime.close()
                process.terminate.assert_called_once()

    def test_request_failure_closes_runtime_without_automatic_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);Image.new('RGB',(80,60)).save(root/'photo.jpg')
            runtime=VisionRuntime(root);process=Mock();process.poll.return_value=None
            runtime.process=process;runtime.endpoint='http://127.0.0.1:1234'
            runtime.opener=Mock();runtime.opener.open.side_effect=TimeoutError()
            with self.assertRaises(TimeoutError):runtime.generate(root/'photo.jpg')
            self.assertIsNone(runtime.process)
            process.terminate.assert_called_once()
            self.assertEqual(runtime.opener.open.call_count,1)

    def test_forked_child_cannot_close_parent_runtime(self):
        runtime=VisionRuntime();runtime.process=Mock()
        with patch('report_general_vlm.os.getpid',return_value=runtime.owner+1):
            runtime.close();runtime.process.terminate.assert_not_called()
        runtime.process=None

    def test_shutdown_does_not_allow_an_automatic_model_restart(self):
        runtime=VisionRuntime();runtime.shutdown()
        with patch('report_general_vlm.subprocess.Popen') as launch:
            with self.assertRaises(RuntimeError):runtime.warm()
            launch.assert_not_called()


if __name__=='__main__':unittest.main()
