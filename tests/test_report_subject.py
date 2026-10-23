import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from report_subject import subject_box

class ReportSubjectTests(unittest.TestCase):
 def test_no_face_or_unusable_face_abstains(self):
  self.assertIsNone(subject_box(None,1920,1080,1/3))
  self.assertIsNone(subject_box([],1920,1080,1/3))
  self.assertIsNone(subject_box([[10,10,2,2]],1920,1080,1/3))
 def test_selects_largest_face_and_includes_body_below_it(self):
  box=subject_box([[10,10,20,25],[100,100,40,50]],1920,1080,1/3)
  self.assertLess(box[0],300);self.assertGreater(box[2],420)
  self.assertLess(box[1],300);self.assertGreater(box[3],450)
 def test_portrait_and_edge_subjects_stay_inside_original(self):
  for width,height in [(1920,1080),(1080,1920)]:
   box=subject_box([[-4,200,70,90]],width,height,1/3)
   self.assertGreaterEqual(box[0],0);self.assertGreaterEqual(box[1],0)
   self.assertLessEqual(box[2],width);self.assertLessEqual(box[3],height)
   self.assertGreater(box[2],box[0]);self.assertGreater(box[3],box[1])

if __name__=='__main__':unittest.main()
