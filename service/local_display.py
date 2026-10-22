"""USB capture on S100, latest-frame inference, GTK fullscreen display."""
from pathlib import Path
import sys,threading,time,json,re,subprocess,urllib.request
from collections import deque
from resource_monitor import ResourceMonitor,corner_action
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
import cv2,numpy as np,gi
gi.require_version('Gtk','3.0')
gi.require_version('PangoCairo','1.0')
from gi.repository import Gtk,Gdk,GdkPixbuf,GLib,Pango,PangoCairo

class Player:
 def __init__(self):
  self.lock=threading.Lock();self.latest=None;self.sequence=0;self.result=None;self.message='等待 USB 摄像头接入…';self.running=True;self.capture_info={};self.painted=None;self.paint_size=None;self.heartbeat=0
  self.window=Gtk.Window(title='S100 实时动漫相机');self.window.set_default_size(1280,720)
  self.window.connect('destroy',lambda *_:Gtk.main_quit());self.window.connect('key-press-event',self.key)
  self.window.connect('window-state-event',self.window_state)
  self.frame_times=deque(maxlen=120);self.resources={};self.panel_visible=False;self.cursor_hidden=False;self.frame_status={}
  self.window.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
  self.window.connect('motion-notify-event',self.pointer_motion)
  css=Gtk.CssProvider();css.load_from_data(b'window {background: black;} label {color: white; font-size: 28px;}')
  Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);self.image=Gtk.DrawingArea();self.image.set_size_request(1,1);self.image.connect('draw',self.draw_frame);self.pixbuf=None;self.label=Gtk.Label(label=self.message)
  self.box.pack_start(self.image,True,True,0);self.box.pack_end(self.label,False,False,12)
  self.overlay=Gtk.Overlay();self.overlay.add(self.box)
  self.panel=Gtk.EventBox();self.panel.set_halign(Gtk.Align.START);self.panel.set_valign(Gtk.Align.START);self.panel.set_margin_start(18);self.panel.set_margin_top(18)
  self.info=Gtk.DrawingArea();self.info.set_size_request(480,360);self.info.connect('draw',self.draw_info);self.info_text='';self.panel.add(self.info)
  panel_css=Gtk.CssProvider();panel_css.load_from_data(b'eventbox {background-color: transparent;border-radius:12px;}')
  self.panel.get_style_context().add_provider(panel_css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);self.info.get_style_context().add_provider(panel_css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.info.show();self.panel.set_no_show_all(True);self.overlay.add_overlay(self.panel);self.overlay.set_overlay_pass_through(self.panel,True);self.window.add(self.overlay)
  self.window.show_all();self.window.fullscreen()
  threading.Thread(target=self.capture,daemon=True).start();threading.Thread(target=self.process,daemon=True).start();GLib.timeout_add(40,self.paint)
  threading.Thread(target=self.monitor_resources,daemon=True).start();GLib.timeout_add(500,self.refresh_info)
 def pointer_motion(self,window,event):
  state=corner_action(event.x,event.y,self.window.get_allocated_width(),self.window.get_allocated_height(),self.panel_visible,max(480,self.panel.get_allocated_width()+36),max(300,self.panel.get_allocated_height()+36))
  self.panel_visible=state['show_panel'];self.panel.set_visible(self.panel_visible)
  if state['hide_cursor']!=self.cursor_hidden:
   self.cursor_hidden=state['hide_cursor'];self.window.get_window().set_cursor(Gdk.Cursor.new_for_display(self.window.get_display(),Gdk.CursorType.BLANK_CURSOR) if self.cursor_hidden else None)
 def monitor_resources(self):
  monitor=ResourceMonitor()
  while self.running:
   self.resources=monitor.sample();time.sleep(1)
 def refresh_info(self):
  r=self.resources;s=self.frame_status;out=s.get('output',[]);fps=s.get('fps',0)
  lines=['实时信息 · S100 BPU',f'输出  {out[0]} × {out[1]}   |   {fps:.1f} FPS' if out else '输出  等待画面',f"采集  {int(self.capture_info.get('width',0))} × {int(self.capture_info.get('height',0))}",f"CPU  {r['cpu_percent']:.1f}%" if 'cpu_percent' in r else 'CPU  采样中']
  lines.append('BPU  '+' / '.join(f'{k}: {v:.0f}%' for k,v in r.get('bpu_percent',{}).items()) if r.get('bpu_percent') else 'BPU  暂无读数')
  if 'bpu_frequency_mhz' in r:lines.append(f"BPU 频率  {r['bpu_frequency_mhz']:.0f} MHz")
  if 'processing_ms' in s:lines.append(f"模型与后处理  {s['processing_ms']:.0f} ms")
  if 'latency_ms' in s:lines.append(f"单帧处理总耗时  {s['latency_ms']:.0f} ms")
  if 'faces' in s:lines.append(f"人脸增强  {s['faces']} 人")
  if 'memory_used_gb' in r:lines.append(f"内存  {r['memory_used_gb']:.2f} / {r['memory_total_gb']:.2f} GB")
  temps=r.get('temperatures',{});soc=[v for k,v in temps.items() if 'cmn' in k];bpu=[v for k,v in temps.items() if 'bpu' in k]
  if soc:lines.append(f'SoC 温度  {max(soc):.1f} °C')
  if bpu:lines.append(f'BPU 温度  {max(bpu):.1f} °C')
  self.info_text='\n'.join(lines);self.info.set_size_request(480,24+27*len(lines));self.info.queue_draw()
  (ROOT/'local-display-resources.json').write_text(json.dumps({'resources':r,'frame':s,'panel_visible':self.panel_visible,'cursor_hidden':self.cursor_hidden,'panel_text':'\n'.join(lines)},ensure_ascii=False,indent=2))
  return True
 def key(self,window,event):
  if event.keyval==Gdk.KEY_Escape:self.window.unfullscreen()
  elif event.keyval in (Gdk.KEY_F11,Gdk.KEY_f):self.window.fullscreen()
 def draw_frame(self,widget,context):
  if self.pixbuf is None:return False
  width=widget.get_allocated_width();height=widget.get_allocated_height();w=self.pixbuf.get_width();h=self.pixbuf.get_height();scale=min(width/w,height/h)
  context.save();context.translate((width-w*scale)/2,(height-h*scale)/2);context.scale(scale,scale)
  Gdk.cairo_set_source_pixbuf(context,self.pixbuf,0,0);context.paint();context.restore()
  return False
 def draw_info(self,widget,context):
  context.save();context.set_source_rgba(0,0,0,0.45)
  context.rectangle(0,0,widget.get_allocated_width(),widget.get_allocated_height());context.fill();context.restore()
  font=Pango.FontDescription('Sans');font.set_absolute_size(19*Pango.SCALE)
  line_layout=PangoCairo.create_layout(context);line_layout.set_font_description(font)
  context.set_source_rgb(1,1,1)
  for row,line in enumerate(self.info_text.splitlines()):
   context.move_to(18,12+row*27);line_layout.set_text(line,-1);PangoCairo.show_layout(context,line_layout)
  return False
 def window_state(self,window,event):
  # The title-bar maximize button should return to kiosk fullscreen too.
  if event.new_window_state&Gdk.WindowState.MAXIMIZED and not event.new_window_state&Gdk.WindowState.FULLSCREEN:
   GLib.idle_add(self.restore_fullscreen)
  (ROOT/'local-display-window.json').write_text(json.dumps({'fullscreen':bool(event.new_window_state&Gdk.WindowState.FULLSCREEN),'time':time.time()}))
 def restore_fullscreen(self):
  self.window.unmaximize();self.window.fullscreen()
  return False
 def capture(self):
  while self.running:
   devices=sorted(Path('/dev/v4l/by-id').glob('*video-index0')) or sorted(Path('/dev').glob('video*'))
   if not devices:time.sleep(1);continue
   cap=None
   for device in devices:
    cap=cv2.VideoCapture(str(device),cv2.CAP_V4L2)
    if cap.isOpened():break
    cap.release();cap=None
   if cap is None:time.sleep(1);continue
   modes=subprocess.run(['v4l2-ctl','-d',str(device),'--list-formats-ext'],capture_output=True,text=True).stdout
   candidates=[];fmt='';size=None
   for line in modes.splitlines():
    m=re.search(r"\[\d+\]: '(.{4})'",line)
    if m:fmt=m[1]
    m=re.search(r'Size: Discrete (\d+)x(\d+)',line)
    if m:size=(int(m[1]),int(m[2]))
    m=re.search(r'\(([\d.]+) fps\)',line)
    if m and size:candidates.append((size[0]*size[1],float(m[1]),fmt,size))
   if candidates:
    _,fps,fmt,(w,h)=max(candidates,key=lambda x:(x[0],x[1],x[2]=='MJPG'))
    cap.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*fmt));cap.set(cv2.CAP_PROP_FRAME_WIDTH,w);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,h);cap.set(cv2.CAP_PROP_FPS,fps)
   cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
   self.capture_info={'device':str(device),'width':cap.get(3),'height':cap.get(4),'fps':cap.get(5)}
   print('CAPTURE',json.dumps(self.capture_info),flush=True)
   while self.running:
    ok,frame=cap.read()
    if not ok:break
    with self.lock:self.latest=frame;self.sequence+=1
   cap.release()
   with self.lock:self.latest=None
   self.message='摄像头已断开，等待重新连接…';time.sleep(1)
 def process(self):
  from inference_pipeline import run_pipeline
  count=0
  def latest():
   with self.lock:return self.sequence,self.latest
  while self.running:
   try:
    for output,metrics in run_pipeline(latest,lambda:self.running):
     self.result=output;count+=1
     now=time.monotonic();self.frame_times.append(now)
     while len(self.frame_times)>2 and self.frame_times[0]<now-3:self.frame_times.popleft()
     fps=(len(self.frame_times)-1)/(now-self.frame_times[0]) if len(self.frame_times)>1 else 1000/max(metrics['latency_ms'],1)
     self.message='';status={'frames':count,'fps':fps,'fps_window_seconds':3,'capture':self.capture_info,'output':[output.shape[1],output.shape[0]],'mirror':True,'backend':'S100 BPU','pipeline':'two-process-gated'}
     status.update(metrics);self.frame_status=status
     if count%10==1:
      (ROOT/'local-display-status.json').write_text(json.dumps(status,indent=2));print('DISPLAY',json.dumps(status),flush=True)
   except Exception as e:self.message='正在恢复推理进程…';print('INFERENCE',str(e),flush=True);time.sleep(1)
 def paint(self):
  self.label.set_text(self.message);self.label.set_visible(bool(self.message))
  if time.monotonic()-self.heartbeat>2:
   self.heartbeat=time.monotonic();(ROOT/'local-display-heartbeat.json').write_text(json.dumps({'message':self.message,'camera':self.capture_info,'has_output':self.result is not None,'time':time.time()}))
  if self.result is not None:
   rgb=self.result;h,w=rgb.shape[:2]
   if self.painted is rgb:return True
   self.painted=rgb
   self.pixbuf=GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgb.tobytes()),GdkPixbuf.Colorspace.RGB,False,8,w,h,w*3)
   self.image.queue_draw()
   if self.panel_visible:self.info.queue_draw()
  return True

if __name__=='__main__':
 player=Player()
 try:Gtk.main()
 finally:player.running=False
