from pathlib import Path
import threading
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,GdkPixbuf,GLib

class PhotoPreview:
 def __init__(self,player,path):
  self.player=player;self.path=Path(path);self.zoom=1.;self.busy=False
  self.source=GdkPixbuf.Pixbuf.new_from_file(str(path))
  self.window=Gtk.Window(title='照片预览');self.window.set_transient_for(player.window);self.window.set_modal(True)
  self.zoom=None;self.offset=[0.,0.];self.drag=None;self.scaled=None
  self.window.set_name('photo-preview')
  css=Gtk.CssProvider();css.load_from_data(b'#photo-preview {background:#10141c;} #photo-preview button {background-image:none;background-color:#283547;color:#ffffff;border:1px solid #61758d;border-radius:8px;padding:12px;} #photo-preview button:hover {background-color:#405773;} #photo-preview button:disabled {background-color:#1c2532;color:#768394;} #photo-preview label {color:#ffffff;font-size:17px;}')
  Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+10)
  box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);self.window.add(box)
  self.view=Gtk.DrawingArea();self.view.set_size_request(1,1);box.pack_start(self.view,True,True,0)
  self.view.connect('draw',self.draw);self.view.connect('size-allocate',self.allocated)
  self.view.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK|Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.SCROLL_MASK)
  self.view.connect('button-press-event',self.press);self.view.connect('button-release-event',self.release);self.view.connect('motion-notify-event',self.motion)
  self.view.connect('scroll-event',self.wheel)
  controls=Gtk.Box(spacing=12);controls.set_halign(Gtk.Align.CENTER);self.buttons=[]
  for title,icon,action in [('缩小','zoom-out-symbolic',lambda *_:self.resize(.8)),('适合屏幕','zoom-fit-best-symbolic',lambda *_:self.fit()),('放大','zoom-in-symbolic',lambda *_:self.resize(1.25)),('打印照片','image-x-generic-symbolic',lambda *_:self.print_item(False)),('打印报纸','x-office-document-symbolic',lambda *_:self.print_item(True)),('关闭','window-close-symbolic',lambda *_:self.window.destroy())]:
   button=Gtk.Button();button.set_image(Gtk.Image.new_from_icon_name(icon,Gtk.IconSize.LARGE_TOOLBAR));button.set_tooltip_text(title);button.get_accessible().set_name(title)
   button.connect('clicked',action);controls.pack_start(button,False,False,0)
   if title=='缩小':self.zoom_out=button
   if title.startswith('打印'):self.buttons.append(button)
  box.pack_start(controls,False,False,8);self.note=Gtk.Label(label='');self.note.set_ellipsize(3);box.pack_start(self.note,False,False,4)
  self.window.connect('key-press-event',self.key);self.window.show_all();self.window.fullscreen()
 def minimum(self):
  return min(max(1,self.view.get_allocated_width())/self.source.get_width(),max(1,self.view.get_allocated_height())/self.source.get_height())
 def allocated(self,*_):
  minimum=self.minimum()
  if self.zoom is None or getattr(self,'at_fit',True):self.zoom=minimum;self.offset=[0.,0.]
  self.zoom=max(minimum,self.zoom);self.render()
 def fit(self):
  self.zoom=self.minimum();self.offset=[0.,0.];self.render();return False
 def resize(self,factor):
  old=self.zoom or self.minimum();self.zoom=max(self.minimum(),min(max(8.,self.minimum()*8),old*factor))
  ratio=self.zoom/old;self.offset=[v*ratio for v in self.offset];self.render()
 def render(self):
  self.at_fit=self.zoom<=self.minimum()+1e-6;self.zoom_out.set_sensitive(not self.at_fit)
  self.view.queue_draw()
 def bounds(self):
  w=self.view.get_allocated_width();h=self.view.get_allocated_height();pw=self.source.get_width()*self.zoom;ph=self.source.get_height()*self.zoom
  self.offset=[max(-max(0,(pw-w)/2),min(max(0,(pw-w)/2),self.offset[0])),max(-max(0,(ph-h)/2),min(max(0,(ph-h)/2),self.offset[1]))]
  return w,h,pw,ph,(w-pw)/2+self.offset[0],(h-ph)/2+self.offset[1]
 def draw(self,widget,c):
  if self.zoom is None:return False
  w,h,pw,ph,x,y=self.bounds();c.set_source_rgb(.04,.05,.07);c.paint()
  c.save();c.translate(x,y);c.scale(self.zoom,self.zoom);Gdk.cairo_set_source_pixbuf(c,self.source,0,0);c.paint();c.restore()
  self.map_box=None
  if not self.at_fit:
   scale=min(190/self.source.get_width(),130/self.source.get_height());mw=self.source.get_width()*scale;mh=self.source.get_height()*scale;mx=w-mw-18;my=h-mh-18
   self.map_box=(mx,my,mw,mh)
   c.set_source_rgba(0,0,0,.8);c.rectangle(mx-5,my-5,mw+10,mh+10);c.fill()
   c.save();c.translate(mx,my);c.scale(scale,scale);Gdk.cairo_set_source_pixbuf(c,self.source,0,0);c.paint();c.restore()
   vx=max(0,-x)/pw*mw;vy=max(0,-y)/ph*mh;vw=min(w,pw)/pw*mw;vh=min(h,ph)/ph*mh
   c.set_source_rgb(.2,.85,1);c.set_line_width(2);c.rectangle(mx+vx,my+vy,vw,vh);c.stroke()
  return False
 def press(self,widget,event):
  if event.button!=1 or self.at_fit:return False
  box=getattr(self,'map_box',None)
  self.map_drag=bool(box and box[0]<=event.x<=box[0]+box[2] and box[1]<=event.y<=box[1]+box[3])
  self.drag=(event.x,event.y,*self.offset)
  if self.map_drag:self.move_map(event.x,event.y)
  widget.get_window().set_cursor(Gdk.Cursor.new_for_display(widget.get_display(),Gdk.CursorType.FLEUR));return True
 def move_map(self,x,y):
  mx,my,mw,mh=self.map_box;pw=self.source.get_width()*self.zoom;ph=self.source.get_height()*self.zoom
  self.offset=[(.5-(x-mx)/mw)*pw,(.5-(y-my)/mh)*ph];self.view.queue_draw()
 def motion(self,widget,event):
  if self.drag:
   if self.map_drag:self.move_map(event.x,event.y)
   else:self.offset=[self.drag[2]+event.x-self.drag[0],self.drag[3]+event.y-self.drag[1]];self.view.queue_draw()
   return True
  return False
 def release(self,widget,event):
  self.drag=None;widget.get_window().set_cursor(None);return True
 def wheel(self,widget,event):
  if event.direction==Gdk.ScrollDirection.UP:self.resize(1.25)
  elif event.direction==Gdk.ScrollDirection.DOWN:self.resize(.8)
  return True
 def key(self,widget,event):
  if event.keyval==Gdk.KEY_Escape:self.window.destroy();return True
  return False
 def print_item(self,paper):
  if self.busy:return
  self.busy=True
  for button in self.buttons:button.set_sensitive(False)
  self.note.set_text('正在提交打印…')
  printer=self.player.festival_settings['printer']
  def worker():
   try:
    from festival import submit_print
    if paper:
     target=self.path.with_name('newspaper.pdf')
     if not target.is_file():raise RuntimeError('这张照片的报纸尚未生成，请稍后再试')
    else:
     from PIL import Image,ImageOps
     from reportlab.pdfgen import canvas
     from reportlab.lib.utils import ImageReader
     target=self.path.with_name('photo-print.pdf')
     with Image.open(self.path) as original:
      photo=ImageOps.exif_transpose(original).convert('RGB');w,h=148/25.4*72,210/25.4*72
      if photo.width>photo.height:w,h=h,w
      scale=min((w-24)/photo.width,(h-24)/photo.height);pw,ph=photo.width*scale,photo.height*scale
      c=canvas.Canvas(str(target),pagesize=(w,h));c.drawImage(ImageReader(photo),(w-pw)/2,(h-ph)/2,pw,ph);c.showPage();c.save()
    result=submit_print(target,printer=printer);message='已提交一份'+('报纸' if paper else '照片')+'：'+result
   except Exception as error:message='打印失败：'+str(error)
   GLib.idle_add(self.finished,message)
  threading.Thread(target=worker,daemon=True).start()
 def finished(self,message):
  self.busy=False
  if self.window.get_visible():
   self.note.set_text(message)
   for button in self.buttons:button.set_sensitive(True)
  return False

def connect_gallery(player):
 player.gallery.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
 def clicked(widget,event):
  if event.button!=1:return False
  geometry=player.gallery_geometry();step=geometry['row_height']+geometry['gap'];index=int(event.y//step)
  if event.y%step>=geometry['row_height']:return False
  if 0<=index<min(geometry['count'],len(player.gallery_paths)):
   try:PhotoPreview(player,player.gallery_paths[index])
   except Exception as error:player.print_note.set_text('无法打开照片：'+str(error))
  return True
 player.gallery.connect('button-press-event',clicked)
