import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from festival import GestureLatch,submit_print,victory,Festival,gesture_regions
import numpy as np,threading,queue

class FestivalTests(unittest.TestCase):
 def test_half_second_confirmation_tolerates_one_missed_sample(self):
  latch=GestureLatch()
  self.assertFalse(latch.update(True,0))
  self.assertFalse(latch.update(False,.18))
  self.assertFalse(latch.update(True,.36))
  self.assertTrue(latch.update(True,.54))
 def test_long_gap_restarts_confirmation(self):
  latch=GestureLatch()
  self.assertFalse(latch.update(True,0))
  self.assertFalse(latch.update(False,.8))
  self.assertFalse(latch.update(True,1))
  self.assertFalse(latch.update(True,1.2))
  self.assertTrue(latch.update(True,1.5))
 def test_continuous_half_second_required(self):
  latch=GestureLatch()
  self.assertFalse(latch.update(True,0))
  self.assertFalse(latch.update(True,.3))
  self.assertFalse(latch.update(True,.49))
  self.assertTrue(latch.update(True,.5))
  self.assertFalse(latch.update(True,.8))
 def test_brief_dropout_cannot_rearm_shutter(self):
  latch=GestureLatch()
  self.assertFalse(latch.update(True,0))
  self.assertTrue(latch.update(True,.5))
  self.assertFalse(latch.update(False,.8))
  self.assertFalse(latch.update(True,1))
  self.assertFalse(latch.update(False,1.8))
  self.assertFalse(latch.update(True,2))
 def test_global_scan_reaches_all_corners_first(self):
  for w,h in [(1920,1080),(1080,1920)]:
   regions=gesture_regions(w,h)
   self.assertEqual(len(regions),len(set(regions)))
   for x,y in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]:
    self.assertTrue(any(a<=x<c and b<=y<d for a,b,c,d in regions[:4]))
 def test_distant_hand_windows_cover_landscape_and_portrait(self):
  for width,height in [(1920,1080),(1080,1920),(640,480)]:
   covered=np.zeros((height,width),dtype=bool)
   for x1,y1,x2,y2 in gesture_regions(width,height):
    self.assertTrue(0<=x1<x2<=width and 0<=y1<y2<=height)
    self.assertLessEqual(x2-x1,min(width,height)*.40)
    covered[y1:y2,x1:x2]=True
   self.assertTrue(covered.all())
 def test_distant_hand_fits_inside_overlapping_window(self):
  regions=gesture_regions(1920,1080)
  # A small hand must not be lost just because it crosses a tile boundary.
  for x in range(40,1881,40):
   for y in range(40,1041,40):
    self.assertTrue(any(a<=x-35 and b<=y-35 and c>=x+35 and d>=y+35 for a,b,c,d in regions))
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
  self.assertIn('orientation-requested=3',calls[0])
  self.assertIn('media-type=stationery',calls[0])
  self.assertIn('media-source=auto',calls[0])
 def test_ambiguous_failure_is_not_retried(self):
  calls=[]
  def runner(*a,**kw):
   calls.append(a);raise TimeoutError('submission uncertain')
  with self.assertRaises(TimeoutError):submit_print('test.pdf',runner)
  self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
