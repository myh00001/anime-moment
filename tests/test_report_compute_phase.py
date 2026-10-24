import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
import inference_pipeline
from festival import Festival
from local_report import GeneralVLMReporter,report_fact_sentence


class ComputePhaseTests(unittest.TestCase):
    def test_pipeline_does_not_reload_workers_after_manual_close_during_report(self):
        state={'running':True}
        def close(_):state['running']=False
        with patch('inference_pipeline._pipeline_session') as session,patch('inference_pipeline.time.sleep',side_effect=close):
            self.assertEqual(list(inference_pipeline.run_pipeline(lambda:None,lambda:state['running'],paused=lambda:True)),[])
            session.assert_not_called()

    def test_many_capture_cycles_release_session_before_report_and_avoid_recursion(self):
        state={'paused':False,'running':True,'sessions':0};events=[]
        def session(*args):
            state['sessions']+=1
            try:yield state['sessions']
            finally:events.append(('closed',state['sessions']))
            state['paused']=True
        def sleep(_):
            self.assertEqual(events[-1][0],'closed')
            state['paused']=False
            if state['sessions']>=1100:state['running']=False
        with patch('inference_pipeline._pipeline_session',side_effect=session),patch('inference_pipeline.time.sleep',side_effect=sleep):
            result=list(inference_pipeline.run_pipeline(lambda:None,lambda:state['running'],paused=lambda:state['paused']))
        self.assertEqual(len(result),1100)

    def test_gesture_model_released_before_report_gate_opens(self):
        festival=Festival.__new__(Festival)
        festival.running=Mock(side_effect=[True,False]);festival.ai_busy_at=1
        festival.gesture_released=threading.Event();festival.latest=Mock()
        detector=SimpleNamespace(runtime=object(),size=384,threshold=.5)
        with patch('festival.time.sleep'):
            festival.yolo_gesture_loop(detector)
        self.assertIsNone(detector.runtime)
        self.assertTrue(festival.gesture_released.is_set())
        festival.latest.assert_not_called()

    def test_context_generation_runs_in_parallel_with_original_image_observation(self):
        started=threading.Event()
        def background(*args):
            started.set();return 'AI将影像化为科技节纪念。'
        def observe(photo):
            self.assertEqual(photo,'/capture/original.jpg')
            self.assertTrue(started.wait(1))
            return {'text':'照片中的人物面带微笑。','backend':'general VLM','model':'InternVL3-2B','seconds':1}
        with patch('local_report.warm_local_model'),patch('local_report.LocalReporter.complete',side_effect=background),patch('report_general_vlm.generate',side_effect=observe):
            text=GeneralVLMReporter().generate('/capture/original.jpg')
        self.assertIn('人物面带微笑',text);self.assertIn('AI将影像',text)

    def test_incomplete_last_clause_and_unrequested_age_are_not_used(self):
        text='照片中显示的是一个房间的角落，有一个衣架上挂着几件衣物，旁边有一个'
        self.assertEqual(report_fact_sentence(text),'画面中显示的是一个房间的角落，有一个衣架上挂着几件衣物。')
        self.assertEqual(report_fact_sentence('照片中，一位年轻女性面向镜头。'),'画面中，人物面向镜头。')


if __name__=='__main__':unittest.main()
