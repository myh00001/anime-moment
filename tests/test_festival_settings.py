import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from festival_settings import DEFAULT_OPTIONS,load_options,save_options,wall_geometry,banner_geometry
from festival import dispatch_output,submit_print
from festival import Festival

class PhotoWallSettingsTests(unittest.TestCase):
 def test_banner_layout_is_bounded_and_preserves_preview_space(self):
  for width,height in [(1920,1080),(1080,1920),(640,360)]:
   for count in [0,1,3,8,20]:
    banner=banner_geometry(width,height,0,count)
    self.assertGreater(banner,0);self.assertLess(banner,height)
    self.assertEqual(banner,banner_geometry(width,height,0,count))
  banner=banner_geometry(1920,1080)
  wall=wall_geometry(1920,1080-banner)['width']
  self.assertLess(abs((1920-wall-14)/(1080-banner)-16/9),.01)
 def test_rows_fit_landscape_portrait_and_small_windows(self):
  for w,h in [(1920,1080),(1080,1920),(640,360),(200,120)]:
   for n in [0,1,3,7,20]:
    for aspect in [16/9,9/16]:
     g=wall_geometry(w,h,n,aspect)
     self.assertLessEqual(g['row_height']*g['count']+g['gap']*(g['count']-1),h)
     self.assertLessEqual(g['width'],w*.45 if n else w*.25)
 def test_width_changes_with_row_count(self):
  fewer=wall_geometry(1920,1080,3);more=wall_geometry(1920,1080,8)
  self.assertGreater(fewer['width'],more['width'])
 def test_options_survive_restart_and_bad_save_preserves_them(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'settings.json'
   options={'gallery_count':5,'print_enabled':False,'printer':'Other_Printer','banner_height':180,'ai_report':True}
   save_options(path,options);self.assertEqual(load_options(path),options)
   with self.assertRaises(ValueError):save_options(path,dict(options,gallery_count=99))
   self.assertEqual(load_options(path),options)
 def test_pdf_only_never_submits_a_job(self):
  def forbidden(*args,**kwargs):raise AssertionError('PDF-only mode submitted print')
  result=dispatch_output('photo.pdf',dict(DEFAULT_OPTIONS,print_enabled=False),forbidden)
  self.assertEqual(result['state'],'pdf_only')
 def test_selected_printer_is_used(self):
  calls=[]
  def submit(pdf,printer):calls.append((pdf,printer));return 'job-123'
  result=dispatch_output('photo.pdf',dict(DEFAULT_OPTIONS,printer='New_Printer'),submit)
  self.assertEqual(calls,[('photo.pdf','New_Printer')]);self.assertEqual(result['state'],'submitted')
 def test_queued_capture_keeps_its_original_print_options(self):
  import queue,threading,numpy as np
  options=dict(DEFAULT_OPTIONS,print_enabled=False,ai_report=True)
  f=Festival.__new__(Festival);f.lock=threading.Lock();f.min_sequence=10;f.jobs=queue.Queue();f.configuration=lambda:options
  raw=np.full((3,4,3),123,np.uint8)
  f.accept(np.zeros((2,2,3),np.uint8),10,raw);raw[:]=0;options['print_enabled']=True;options['ai_report']=False
  rgb,captured,original=f.jobs.get_nowait();self.assertTrue((original==123).all());self.assertFalse(captured['print_enabled']);self.assertTrue(captured['ai_report'])

 def test_report_receives_original_camera_pixels_and_pdf_receives_anime(self):
  import queue,threading,numpy as np
  from unittest.mock import patch
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder:
   f=Festival.__new__(Festival);f.lock=threading.Lock();f.min_sequence=10;f.jobs=queue.Queue()
   f.configuration=lambda:dict(DEFAULT_OPTIONS,print_enabled=False,ai_report=True)
   f.deadline=None;f.running=lambda:False;f.directory=Path(folder);f.history=[];f.notify=lambda photo:None
   anime=np.zeros((4,4,3),np.uint8);anime[:,:,0]=255
   raw=np.zeros((4,4,3),np.uint8);raw[:,:,0]=255 # BGR blue, different from anime RGB red.
   f.accept(anime,9,raw);self.assertTrue(f.jobs.empty())
   f.accept(anime,10,raw)
   drained=[];f.wait_inference_idle=lambda:drained.append(True) or True
   def report(path,enabled):
    self.assertEqual(drained,[True])
    self.assertTrue(enabled);self.assertEqual(path.name,'original.jpg')
    self.assertGreater(f.ai_busy_at,0);self.assertFalse(f.trigger())
    pixel=Image.open(path).getpixel((0,0));self.assertGreater(pixel[2],240);self.assertLess(pixel[0],10)
    return {'state':'generated','text':'test'}
   def paper(photo,pdf,**kwargs):
    self.assertEqual(photo.name,'photo.jpg')
    self.assertGreater(Image.open(photo).getpixel((0,0))[0],240)
    pdf.write_bytes(b'test')
   with patch('festival.make_report',side_effect=report),patch('festival.newspaper',side_effect=paper):f.save_loop()
   self.assertEqual(len(list(Path(folder).glob('*/original.jpg'))),1)
   self.assertEqual(f.ai_busy_at,0);self.assertTrue(f.trigger())

 def test_ai_disabled_still_saves_original_and_anime(self):
  import queue,threading,numpy as np
  from unittest.mock import patch
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder:
   f=Festival.__new__(Festival);f.lock=threading.Lock();f.min_sequence=10;f.jobs=queue.Queue()
   f.configuration=lambda:dict(DEFAULT_OPTIONS,print_enabled=False,ai_report=False)
   f.deadline=None;f.running=lambda:False;f.directory=Path(folder);f.history=[];f.notify=lambda photo:None
   anime=np.zeros((4,4,3),np.uint8);anime[:,:,0]=255
   raw=np.zeros((4,4,3),np.uint8);raw[:,:,0]=255 # BGR blue, different from anime RGB red.
   f.accept(anime,9,raw);self.assertTrue(f.jobs.empty())
   f.accept(anime,10,raw)
   def report(path,enabled):
    self.assertFalse(enabled);self.assertEqual(path.name,'original.jpg')
    pixel=Image.open(path).getpixel((0,0));self.assertGreater(pixel[2],240);self.assertLess(pixel[0],10)
    return {'state':'generated','text':'test'}
   def paper(photo,pdf,**kwargs):
    self.assertEqual(photo.name,'photo.jpg')
    self.assertGreater(Image.open(photo).getpixel((0,0))[0],240)
    pdf.write_bytes(b'test')
   with patch('festival.make_report',side_effect=report),patch('festival.newspaper',side_effect=paper):f.save_loop()
   self.assertEqual(len(list(Path(folder).glob('*/original.jpg'))),1)

 def test_ai_failure_unlocks_capture_without_pickup_prompt(self):
  import queue,threading,numpy as np
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder:
   f=Festival.__new__(Festival);f.lock=threading.Lock();f.min_sequence=1;f.deadline=None;f.jobs=queue.Queue()
   f.configuration=lambda:dict(DEFAULT_OPTIONS,ai_report=True,print_enabled=False)
   f.deadline=None;f.running=lambda:False;f.directory=Path(folder);f.history=[];f.notify=lambda photo:None
   f.accept(np.zeros((2,2,3),np.uint8),1)
   with patch('festival.make_report',side_effect=RuntimeError('test')):f.save_loop()
   self.assertEqual(f.ai_busy_at,0);self.assertEqual(f.pickup_at,0);self.assertTrue(f.trigger())

 def test_busy_anime_timeout_uses_fixed_copy_and_unlocks(self):
  import queue,threading,numpy as np,json
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder:
   f=Festival.__new__(Festival);f.lock=threading.Lock();f.min_sequence=1;f.deadline=None;f.jobs=queue.Queue()
   f.configuration=lambda:dict(DEFAULT_OPTIONS,ai_report=True,print_enabled=False)
   f.running=lambda:False;f.directory=Path(folder);f.history=[];f.notify=lambda photo:None;f.wait_inference_idle=lambda:False
   f.accept(np.zeros((2,2,3),np.uint8),1)
   with patch('festival.make_report') as report,patch('festival.newspaper') as newspaper:
    f.save_loop();report.assert_not_called();self.assertIsNone(newspaper.call_args.kwargs['report'])
   result=json.loads(next(Path(folder).glob('*/record.json')).read_text())
   self.assertEqual(result['state'],'pdf_only');self.assertEqual(result['ai_report']['reason'],'InferenceNotIdle')
   self.assertEqual(f.ai_busy_at,0)

if __name__=='__main__':unittest.main()
