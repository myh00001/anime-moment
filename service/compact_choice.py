"""Compact searchable GTK3 choices without oversized native menu positioning."""
from gi.repository import Gtk,GObject,Pango
class CompactChoice(Gtk.MenuButton):
 __gsignals__={'changed':(GObject.SignalFlags.RUN_FIRST,None,())}
 def __init__(self):
  super().__init__();self._items=[];self._active=None
  line=Gtk.Box(spacing=6);self.label=Gtk.Label(label='请选择',xalign=0);self.label.set_ellipsize(Pango.EllipsizeMode.END);self.label.set_max_width_chars(22);line.pack_start(self.label,True,True,0);line.pack_end(Gtk.Image.new_from_icon_name('pan-down-symbolic',Gtk.IconSize.MENU),False,False,0);self.add(line);line.show_all()
  popup=Gtk.Popover.new(self);popup.set_name('compact-choice-popup');popup.set_position(Gtk.PositionType.BOTTOM);self.set_popover(popup)
  box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);box.set_border_width(8);popup.add(box)
  self.search=Gtk.SearchEntry();self.search.set_placeholder_text('搜索选项');box.pack_start(self.search,False,False,0)
  scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);scroll.set_min_content_height(120);scroll.set_max_content_height(260);scroll.set_propagate_natural_height(True);scroll.set_size_request(260,-1);box.pack_start(scroll,True,True,0)
  self.rows=Gtk.ListBox();self.rows.set_selection_mode(Gtk.SelectionMode.SINGLE);scroll.add(self.rows)
  self.rows.set_filter_func(lambda row:not self.search.get_text().strip() or self.search.get_text().strip().casefold() in row.choice_text.casefold())
  self.search.connect('search-changed',lambda *_:self.rows.invalidate_filter());self.rows.connect('row-activated',self._select_row)
  self.search.connect('activate',self._activate_first)
  popup.connect('show',self._open);box.show_all()
  css=Gtk.CssProvider();css.load_from_data(b'#compact-choice-popup {background-color:#273240;color:#ffffff;} #compact-choice-popup label {color:#ffffff;font-size:16px;} #compact-choice-popup list,#compact-choice-popup row {background-color:#273240;color:#ffffff;} #compact-choice-popup row:hover,#compact-choice-popup row:selected {background-color:#47647b;} #compact-choice-popup entry {background-image:none;background-color:#354255;color:#ffffff;}')
  Gtk.StyleContext.add_provider_for_screen(self.get_screen(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+30)
 def _open(self,*_):
  self.search.set_text('');self.rows.invalidate_filter();self.search.grab_focus()
 def _activate_first(self,*_):
  row=next((r for r in self.rows.get_children() if r.get_child_visible()),None)
  if row:self._select_row(self.rows,row)
 def _select_row(self,box,row):
  self.set_active_id(row.choice_id);self.get_popover().popdown();self.set_active(False)
 def append(self,key,label):
  key=str(key);self._items.append((key,label));row=Gtk.ListBoxRow();row.choice_id=key;row.choice_text=label
  text=Gtk.Label(label=label,xalign=0);text.set_margin_start(8);text.set_margin_end(8);text.set_margin_top(7);text.set_margin_bottom(7);row.add(text);self.rows.add(row);row.show_all()
 def remove_all(self):
  for row in self.rows.get_children():self.rows.remove(row)
  self._items=[];self._active=None;self.label.set_text('请选择')
 def set_active_id(self,key):
  key=str(key) if key is not None else None
  item=next((item for item in self._items if item[0]==key),None)
  if item is None:return False
  changed=self._active!=key;self._active=key;self.label.set_text(item[1]);self.set_tooltip_text(item[1])
  if changed:self.emit('changed')
  return True
 def set_active(self,index):
  # MenuButton uses a boolean for its own pressed state.
  if type(index) is bool:return super().set_active(index)
  if 0<=index<len(self._items):self.set_active_id(self._items[index][0])
 def get_active_id(self):return self._active
 def get_active_text(self):return next((label for key,label in self._items if key==self._active),None)
 def get_model(self):return self._items
