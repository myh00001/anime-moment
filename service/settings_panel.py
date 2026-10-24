"""Organize existing camera controls without changing saved option formats."""
from gi.repository import Gtk,GLib

def organize_settings(p):
 root=p.panel_content
 # A scroller with horizontal scrolling otherwise advertises only scrollbar width.
 p.panel_scroll.set_size_request(480,-1)
 for canvas in (p.image,p.banner,p.gallery,p.info):
  if not canvas.get_realized():canvas.set_has_window(False)
 p.panel.set_visible_window(True)
 header=Gtk.Box(spacing=10);header.set_margin_start(16);header.set_margin_end(16);header.set_margin_top(14);header.set_margin_bottom(14)
 title=Gtk.Label(label='相机设置',xalign=0);header.pack_start(title,True,True,0)
 pin=Gtk.ToggleButton(label='固定面板');pin.set_tooltip_text('固定后移开鼠标也保持显示');pin.connect('toggled',lambda b:setattr(p,'panel_pinned',b.get_active()));header.pack_end(pin,False,False,0)
 root.pack_start(header,False,False,0);root.reorder_child(header,0)
 # Detach grid controls before regrouping; all existing callbacks remain bound.
 old=p.festival_expander;grid=old.get_child();cells={}
 for child in grid.get_children():
  pos=(grid.child_get_property(child,'left-attach'),grid.child_get_property(child,'top-attach'))
  cells[pos]=child;grid.remove(child)
 root.remove(old)
 def section(title,expanded=False):
  exp=Gtk.Expander(label=title);exp.set_expanded(expanded);exp.set_margin_start(16);exp.set_margin_end(16);exp.set_margin_bottom(14)
  body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);body.set_margin_top(12);exp.add(body);root.pack_start(exp,False,False,0)
  exp.connect('notify::expanded',lambda *_:GLib.idle_add(p.resize_panel));return exp,body
 def row(body,*widgets):
  line=Gtk.Box(spacing=10)
  for w in widgets:line.pack_start(w,True,True,0)
  body.pack_start(line,False,False,0)
 # Keep frame settings as one independent category with its own save action.
 p.settings_expander.set_label('画面与摄像头');root.reorder_child(p.settings_expander,1)
 _,body=section('拍照与 AI 报道',True)
 capture=Gtk.Button(label='拍照 · 3 秒倒计时');capture.connect('clicked',lambda *_:p.festival.trigger() if p.festival else None);body.pack_start(capture,False,False,0)
 body.pack_start(cells[(0,7)],False,False,0);body.pack_start(cells[(0,8)],False,False,0)
 _,body=section('打印与文件保存',True)
 p.pdf_only.set_label('拍照后自动打印纪念报纸');p.pdf_only.set_active(p.festival_settings['print_enabled'])
 # Existing code uses the inverse checkbox value. Keep its API through an adapter
 # on the player, while presenting a positive print switch to the user.
 original=p.pdf_only
 class PrintChoice:
  def get_active(self):return not original.get_active()
 p.pdf_only=PrintChoice()
 original.connect('toggled',lambda b:p.printer_choice.set_sensitive(b.get_active()));p.printer_choice.set_sensitive(original.get_active())
 body.pack_start(original,False,False,0);row(body,cells[(0,2)],cells[(1,2)]);body.pack_start(cells[(0,3)],False,False,0)
 note=Gtk.Label(label='每次拍照都保存原图、动漫图和报纸 PDF。',xalign=0);note.set_line_wrap(True);note.set_max_width_chars(28);body.pack_start(note,False,False,0)
 queue_label=Gtk.Label(label='打印队列：读取中…',xalign=0);body.pack_start(queue_label,False,False,0)
 p.queue_count_label=queue_label;p.queue_count_pending=False;p.queue_count_serial=0
 def refresh_queue(*_):
  import threading
  if not p.running:return False
  if p.queue_count_pending:return True
  printer=p.printer_choice.get_active_id() or p.festival_settings['printer']
  p.queue_count_pending=True;p.queue_count_serial+=1;serial=p.queue_count_serial
  def worker():
   try:
    from print_queue import queue_count
    count=queue_count(printer);text=f'打印队列：{count} 个任务'
   except Exception:text='打印队列：暂时无法读取'
   def finished():
    p.queue_count_pending=False
    selected=p.printer_choice.get_active_id() or p.festival_settings['printer']
    if p.running and selected==printer:queue_label.set_text(text)
    return False
   GLib.idle_add(finished)
  threading.Thread(target=worker,daemon=True).start();return True
 p.printer_choice.connect('changed',refresh_queue);GLib.timeout_add_seconds(3,refresh_queue);refresh_queue()
 clear=Gtk.Button(label='清空打印队列');clear.set_tooltip_text('取消当前所选打印机的全部未完成任务，保留照片和 PDF')
 def clear_clicked(button):
  import threading
  printer=p.printer_choice.get_active_id() or p.festival_settings['printer']
  button.set_sensitive(False);p.print_note.set_text('正在清空打印队列…')
  def worker():
   try:
    from print_queue import clear_queue
    clear_queue(printer);message='打印队列已清空，照片和 PDF 已保留。'
   except Exception as error:message='清空失败：'+str(error)
   def finished():
    button.set_sensitive(True);p.print_note.set_text(message);refresh_queue()
    if p.festival:p.festival.status=message
    return False
   GLib.idle_add(finished)
  threading.Thread(target=worker,daemon=True).start()
 clear.connect('clicked',clear_clicked);body.pack_start(clear,False,False,0)
 p.clear_print_queue_button=clear
 body.pack_start(p.print_note,False,False,0)
 _,weather_body=section('城市与天气')
 from weather_panel import build_weather_panel
 p.weather_controls=build_weather_panel(p,weather_body)
 _,body=section('照片墙与广告栏')
 row(body,cells[(0,0)],cells[(1,0)]);body.pack_start(cells[(2,0)],False,False,0)
 row(body,cells[(0,6)],cells[(1,6)]);body.pack_start(cells[(2,6)],False,False,0);body.pack_start(p.festival_note,False,False,0)
 footer=Gtk.Box(spacing=8);footer.set_margin_start(16);footer.set_margin_end(16);footer.set_margin_bottom(14)
 save=cells[(1,3)];save.set_label('保存拍照、打印和布局设置');footer.pack_start(save,True,True,0);root.pack_start(footer,False,False,0)
 root.remove(p.info);_,body=section('运行状态与性能');body.pack_start(p.info,False,False,0)
 p.panel_scroll.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC)
 css=Gtk.CssProvider();css.load_from_data(b'#camera-settings {background-color:rgba(32,38,48,0.62);border-radius:12px;} #camera-settings label {color:#f2f5fa;font-size:16px;} #camera-settings button,#camera-settings combobox button,#camera-settings spinbutton,#camera-settings entry {background-image:none;background-color:#354255;color:#ffffff;border:1px solid #617087;border-radius:6px;} #camera-settings button:hover {background-color:#475b73;} #camera-settings button:checked {background-color:#286a68;} #camera-settings button:disabled {color:#8895a6;} #camera-settings expander {color:#ffffff;}')
 Gtk.StyleContext.add_provider_for_screen(p.window.get_screen(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+20)
