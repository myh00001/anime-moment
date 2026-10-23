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
   options={'gallery_count':5,'print_enabled':False,'printer':'Other_Printer','banner_height':180}
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
  options=dict(DEFAULT_OPTIONS,print_enabled=False)
  f=Festival.__new__(Festival);f.lock=threading.Lock();f.min_sequence=10;f.jobs=queue.Queue();f.configuration=lambda:options
  f.accept(np.zeros((2,2,3),np.uint8),10);options['print_enabled']=True
  rgb,captured=f.jobs.get_nowait();self.assertFalse(captured['print_enabled'])

if __name__=='__main__':unittest.main()
