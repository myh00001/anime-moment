import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from festival import GestureLatch,submit_print,victory,Festival
import numpy as np,threading,queue

class FestivalTests(unittest.TestCase):
 def test_victory_geometry_survives_rotation(self):
  p=np.zeros((21,3))
  for base,x in [(5,-1.5),(9,-.5),(13,.5),(17,1.5)]:
   for joint in range(4):p[base+joint]=[x,-2-joint,0]
  for base in [13,17]:p[base+3]=[p[base,0],-1,0]
  self.assertTrue(victory(p))
  rotation=np.array([[0,-1,0],[1,0,0],[0,0,1]])
  self.assertTrue(victory(p@rotation*3))
  p[16]=[.5,-5,0];p[20]=[1.5,-5,0]
  self.assertFalse(victory(p))
 def test_photo_waits_for_fresh_frame(self):
  f=Festival.__new__(Festival);f.lock=threading.Lock();f.min_sequence=10;f.jobs=queue.Queue(maxsize=2)
  frame=np.zeros((2,2,3),dtype=np.uint8)
  f.accept(frame,9);self.assertTrue(f.jobs.empty())
  f.accept(frame,10);self.assertEqual(f.jobs.qsize(),1)
  f.accept(frame,11);self.assertEqual(f.jobs.qsize(),1)
 def test_held_gesture_cannot_repeat(self):
  latch=GestureLatch()
  self.assertFalse(latch.update(True,0))
  self.assertTrue(latch.update(True,.5))
  self.assertFalse(latch.update(True,10))
  self.assertFalse(latch.update(False,11))
  self.assertFalse(latch.update(False,12.1))
  self.assertFalse(latch.update(True,13))
  self.assertTrue(latch.update(True,13.5))
 def test_one_print_submission(self):
  calls=[]
  def runner(args,**kwargs):
   calls.append(args)
   from types import SimpleNamespace
   return SimpleNamespace(returncode=0,stdout='request id is S100_Festival-1',stderr='')
  submit_print('test.pdf',runner)
  self.assertEqual(len(calls),1)
  self.assertIn('iso_a5_148x210mm',calls[0][calls[0].index('-o')+1])
  self.assertEqual(calls[0][calls[0].index('-n')+1],'1')
  self.assertIn('orientation-requested=4',calls[0])
 def test_ambiguous_failure_is_not_retried(self):
  calls=[]
  def runner(*a,**kw):
   calls.append(a);raise TimeoutError('submission uncertain')
  with self.assertRaises(TimeoutError):submit_print('test.pdf',runner)
  self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
