import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
import report_ffn


class FfnManifestTests(unittest.TestCase):
    def fixture(self,root):
        local=root/'local-vlm';models=local/'models';models.mkdir(parents=True)
        files={'language_sha256':local/'internvl2b-candidate/language.gguf',
               'binary_sha256':local/'bin/llama-server','worker_sha256':root/'report_ffn_worker.py'}
        config={'version':1,'enabled':True,'binary':'bin/llama-server','models_directory':'models','models':{}}
        for name,path in files.items():
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
            config[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        path=models/'ffn0_t256.hbm';path.write_bytes(b'private-test-model')
        config['models']['0']={'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        (local/'report-ffn.json').write_text(json.dumps(config))
        return config

    def test_disabled_without_manifest_and_accepts_exact_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertIsNone(report_ffn.load_config(root))
            self.fixture(root)
            self.assertEqual(report_ffn.load_config(root)['layers'],[0])

    def test_weight_change_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=self.fixture(root)
            (root/'local-vlm/models/ffn0_t256.hbm').write_bytes(b'wrong-weights')
            with self.assertRaises(ValueError):report_ffn.load_config(root)
            config['binary']='../../outside';(root/'local-vlm/report-ffn.json').write_text(json.dumps(config))
            with self.assertRaises(ValueError):report_ffn.load_config(root)

    def test_missing_layer_execution_cannot_be_reported_as_accelerated(self):
        sidecar=report_ffn.Sidecar('.',{'layers':[0,1]})
        sidecar.stats=lambda:[{'index':1,'layer':0,'seconds':.01}]
        with self.assertRaises(RuntimeError):sidecar.finish(0)

    def test_worker_release_starts_while_writer_can_run(self):
        sidecar=report_ffn.Sidecar('.',{'layers':[0]})
        sidecar.stats=lambda:[{'index':1,'layer':0,'seconds':.01}]
        with patch.object(sidecar,'stop_worker') as stop:
            self.assertEqual(sidecar.finish(0)['calls'],1)
            stop.assert_called_once_with(wait=False)

    def test_async_release_is_joined_without_terminating_twice(self):
        from unittest.mock import Mock
        sidecar=report_ffn.Sidecar('.',{})
        process=Mock();process.poll.return_value=None;sidecar.process=process
        sidecar.stop_worker(wait=False)
        self.assertTrue(sidecar.releasing);process.wait.assert_not_called()
        self.assertIs(sidecar.process,process)
        sidecar.stop_worker()
        process.terminate.assert_called_once();process.wait.assert_called_once_with(timeout=3)
        self.assertIsNone(sidecar.process);self.assertFalse(sidecar.releasing)

    def test_shared_encoder_checks_fragmented_reply_and_capture_sequence(self):
        sidecar=report_ffn.Sidecar('.',{});sidecar.socket='private.sock'
        def connection(sequence):
            body=json.dumps({'state':'encoded','sequence':sequence}).encode()
            packet=struct.pack('<IIIII',0x5346464e,0xfffffffe,0,len(body),0)+body
            class Connection:
                def __enter__(self):self.data=bytearray(packet);return self
                def __exit__(self,*args):pass
                def settimeout(self,value):pass
                def connect(self,value):pass
                def sendall(self,value):pass
                def recv(self,length):
                    count=min(length,3);result=self.data[:count];del self.data[:count];return result
            return Connection()
        with patch.object(report_ffn.socket,'AF_UNIX',1,create=True):
            with patch.object(report_ffn.socket,'socket',return_value=connection(5)):
                self.assertEqual(sidecar.encode('original.jpg','embedding.bin',5)['sequence'],5)
            with patch.object(report_ffn.socket,'socket',return_value=connection(4)):
                with self.assertRaises(ValueError):sidecar.encode('original.jpg','embedding.bin',5)

    def test_forked_child_cannot_stop_parent_sidecar(self):
        sidecar=report_ffn.Sidecar('.',{});sidecar.owner=-1
        class ParentProcess:
            def poll(self):raise AssertionError('Touched parent process')
        sidecar.process=ParentProcess();sidecar.close()

    def test_ffn_failure_retries_same_original_with_cpu_language_binary(self):
        runtime=importlib.import_module('report_general_vlm')
        class Engine:
            ffn=object();binary='experimental';cpu_binary='stable';bpu=True;shutdown_requested=threading.Event()
            def __init__(self):self.photos=[]
            def generate(self,photo):
                self.photos.append(photo)
                if len(self.photos)==1:raise OSError('experimental worker failed')
                return {'text':'same image'}
            def close(self):pass
        engine=Engine()
        with patch.object(runtime,'runtime',return_value=engine):result=runtime.generate('original.jpg')
        self.assertEqual(engine.photos,['original.jpg','original.jpg'])
        self.assertEqual(engine.binary,'stable');self.assertIsNone(engine.ffn)
        self.assertTrue(engine.bpu)
        self.assertEqual(result['acceleration_fallback'],'FFN-OSError')


if __name__=='__main__':unittest.main()
