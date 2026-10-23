import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from local_report import LocalReporter, make_report, PROMPT


class ReportPrefillTests(unittest.TestCase):
    def setUp(self):
        self.environment=patch('local_report.helper_environment',return_value=None)
        self.environment.start();self.addCleanup(self.environment.stop)
    def test_cache_gate_distinguishes_empty_cached_busy_and_unknown_slots(self):
        engine=LocalReporter(starter=Mock())
        for slots,expected in [([{'id':0,'n_ctx':2048}],False),
                               ([{'id':0,'n_ctx':2048,'n_prompt_tokens':None}],False),
                               ([{'id':0,'n_ctx':2048,'n_prompt_tokens':304}],True),
                               ([{'id':0,'n_ctx':2048,'is_processing':True}],True),
                               ([],None),({'unexpected':1},None),([{}],None)]:
            engine.opener=Mock()
            engine.opener.open.return_value=io.BytesIO(json.dumps(slots).encode())
            self.assertIs(engine.writer_cache_ready(.1),expected)
        engine.opener.open.side_effect=OSError('offline')
        self.assertIsNone(engine.writer_cache_ready(.1))

    def test_warm_cache_skips_subject_probe_and_resets_previous_probe(self):
        engine=LocalReporter(starter=Mock());engine.writer_cache_ready=Mock(return_value=True)
        engine.prefill_subject={'subject_visible':False}
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.jpg';photo.write_bytes(b'fixture')
            with patch('report_subject.prepare_subject') as prepare:
                self.assertFalse(engine.can_prefill(photo));prepare.assert_not_called()
        self.assertIsNone(engine.prefill_subject)

    def test_confirmed_no_subject_skips_writer_start_and_vision_process(self):
        engine=LocalReporter(starter=Mock());engine.writer_cache_ready=Mock(return_value=False)
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.jpg';photo.write_bytes(b'fixture')
            with patch('local_report.bpu_available',return_value=True), \
                 patch('report_subject.prepare_subject',return_value={'subject_visible':False,'faces':0}), \
                 patch('report_bpu_caption.model_profile',return_value={'name':'SmolVLM2-500M'}), \
                 patch('local_report.subprocess.Popen') as launch:
                report=make_report(photo,True,engine)
        self.assertEqual(report['state'],'generated');self.assertEqual(report['vision_decoder'],'not run')
        engine.starter.assert_not_called();launch.assert_not_called()

    def test_prefill_only_runs_for_confirmed_empty_cache(self):
        engine=LocalReporter(starter=Mock());engine.wait_ready=Mock();engine.complete=Mock()
        for state in [True,None]:
            engine.writer_cache_ready=Mock(return_value=state);engine.prefill_writer(time.monotonic()+5)
            engine.complete.assert_not_called()
        engine.writer_cache_ready=Mock(return_value=False);engine.prefill_writer(time.monotonic()+5)
        payload=engine.complete.call_args.args[1]
        self.assertEqual(payload['max_tokens'],1)
        self.assertEqual(payload['messages'][0]['content'],PROMPT)
        self.assertNotIn('image',json.dumps(payload))

    def test_vision_failure_waits_for_prefill_before_returning_fallback(self):
        started=threading.Event();release=threading.Event();finished=threading.Event()
        engine=LocalReporter(starter=Mock());engine.can_prefill=Mock(return_value=True);engine.prefill_subject=None
        def prefill(deadline):
            started.set();release.wait(1);time.sleep(.02);finished.set()
        engine.prefill_writer=prefill
        process=Mock();process.returncode=1
        def communicate(**kwargs):
            self.assertTrue(started.wait(1));release.set();return b'',b''
        process.communicate.side_effect=communicate
        with patch('local_report.bpu_available',return_value=True),patch('local_report.subprocess.Popen',return_value=process):
            report=make_report('/local/original.jpg',True,engine)
        self.assertEqual(report['state'],'fallback');self.assertTrue(finished.is_set())

    def test_optional_prefill_failure_does_not_replace_valid_report(self):
        engine=LocalReporter(starter=Mock());engine.can_prefill=Mock(return_value=True);engine.prefill_subject=None
        engine.prefill_writer=Mock(side_effect=OSError('prefill failed'))
        engine.wait_ready=Mock();engine.complete=Mock(return_value='体验者身穿夹克。')
        process=Mock();process.returncode=0
        process.communicate.return_value=(json.dumps({'text':'A jacket.','seconds':1}).encode(),b'')
        with patch('local_report.bpu_available',return_value=True),patch('local_report.subprocess.Popen',return_value=process):
            report=make_report('/local/original.jpg',True,engine)
        self.assertEqual(report['state'],'generated')

    def test_vision_timeout_cleans_process_group_and_joins_prefill(self):
        started=threading.Event();release=threading.Event();finished=threading.Event()
        engine=LocalReporter(starter=Mock());engine.can_prefill=Mock(return_value=True);engine.prefill_subject=None
        def prefill(deadline):
            started.set();release.wait(1);finished.set()
        engine.prefill_writer=prefill
        process=Mock();process.pid=1234
        def timeout(**kwargs):
            self.assertTrue(started.wait(1));raise subprocess.TimeoutExpired('vision',.01)
        calls=[]
        def communicate(**kwargs):
            calls.append(1)
            if len(calls)==1:return timeout(**kwargs)
            return b'',b''
        process.communicate.side_effect=communicate
        with patch('local_report.bpu_available',return_value=True), \
             patch('local_report.subprocess.Popen',return_value=process), \
             patch('local_report.os.killpg',side_effect=lambda *args:release.set(),create=True) as kill:
            report=make_report('/local/original.jpg',True,engine)
        self.assertEqual(report['reason'],'TimeoutError');kill.assert_called_once()
        self.assertTrue(finished.is_set())


if __name__=='__main__':unittest.main()
