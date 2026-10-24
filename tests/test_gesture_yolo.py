import sys,unittest,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from gesture_yolo import decode
class YoloDecodeTests(unittest.TestCase):
 def outputs(self):
  result={}
  for stride in [8,16,32]:
   result[f'boxes_s{stride}']=np.zeros((1,64,1,1),np.float32)
   result[f'classes_s{stride}']=np.full((1,34,1,1),-20,np.float32)
  return result
 def test_background_never_triggers(self):self.assertEqual(decode(self.outputs(),(1,0,0,640,640)),[])
 def test_competing_class_must_win(self):
  out=self.outputs();out['classes_s8'][0,21,0,0]=4;out['classes_s8'][0,14,0,0]=8
  rows=decode(out,(1,0,0,640,640));self.assertEqual([r['class'] for r in rows],['fist'])
 def test_peace_layout_and_clipping(self):
  out=self.outputs();out['classes_s8'][0,22,0,0]=8
  expected=decode(out,(.5,10,20,640,480))
  nhwc={k:v.transpose(0,2,3,1) for k,v in out.items()}
  self.assertEqual(expected,decode(nhwc,(.5,10,20,640,480)))
  self.assertEqual(expected[0]['class'],'peace_inverted')
  self.assertTrue(all(v>=0 for v in expected[0]['box']))
if __name__=='__main__':unittest.main()
