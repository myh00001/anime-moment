"""City and weather controls for the translucent GTK settings panel."""
import json
from pathlib import Path
from gi.repository import Gtk,GLib
from weather_settings import load,save,WEATHER_CHOICES
from festival_weather import weather_label
from compact_choice import CompactChoice

def build_weather_panel(p,body):
 root=Path(__file__).resolve().parent;path=root/'weather-settings.json';settings=load(path)
 regions=json.loads((root/'china-cities.json').read_text(encoding='utf-8-sig'))
 def combo(items):
  widget=CompactChoice()
  for key,label in items:widget.append(str(key),label)
  return widget
 def row(label,widget):
  line=Gtk.Box(spacing=10);line.pack_start(Gtk.Label(label=label,xalign=0),False,False,0);line.pack_start(widget,True,True,0);body.pack_start(line,False,False,0)
 city_mode=combo([('auto','自动 · IP 定位'),('manual','手动选择城市')]);city_mode.set_active_id(settings['city_mode']);row('城市来源',city_mode)
 province=combo([(r['code'],r['name']) for r in regions]);city=CompactChoice();district=CompactChoice()
 row('省／直辖市',province);row('城市',city);row('区县（可选）',district)
 def current_province():return next((r for r in regions if r['code']==province.get_active_id()),regions[0])
 def current_city():return next((c for c in current_province()['children'] if c['code']==city.get_active_id()),current_province()['children'][0])
 def change_city(*_):
  district.remove_all();district.append('','全市')
  for d in current_city().get('children',[]):district.append(d['code'],d['name'])
  district.set_active(0)
 def change_province(*_):
  city.remove_all()
  for c in current_province()['children']:city.append(c['code'],c['name'])
  city.set_active(0)
 province.connect('changed',change_province);city.connect('changed',change_city)
 province.set_active_id(next((r['code'] for r in regions if r['name']==settings['province']),regions[0]['code']))
 city.set_active_id(next((c['code'] for c in current_province()['children'] if c['name']==settings['city']),current_province()['children'][0]['code']))
 district.set_active_id(next((d['code'] for d in current_city().get('children',[]) if d['name']==settings['district']),''))
 print_parts=Gtk.Box(spacing=8);print_province=Gtk.CheckButton(label='省');print_city=Gtk.CheckButton(label='市');print_district=Gtk.CheckButton(label='区县')
 for key,widget in [('print_province',print_province),('print_city',print_city),('print_district',print_district)]:widget.set_active(settings[key]);print_parts.pack_start(widget,False,False,0)
 row('报纸打印地点',print_parts)
 preview=Gtk.Label(xalign=0);preview.set_line_wrap(True);preview.set_max_width_chars(27);body.pack_start(preview,False,False,0)
 def update_preview(*_):
  from festival_weather import format_location
  if city_mode.get_active_id()=='auto':preview.set_text('自动规则：直辖市打印市＋区；其他地区打印省＋市。');return
  parts=dict(province=current_province()['name'],city=current_city()['name'],district='' if not district.get_active_id() else district.get_active_text())
  flags=dict(city_mode='manual',print_province=print_province.get_active(),print_city=print_city.get_active(),print_district=print_district.get_active())
  preview.set_text('地点预览：'+(format_location(parts,flags) or '不打印地点'))
 for widget in (city_mode,province,city,district):widget.connect('changed',update_preview)
 for widget in (print_province,print_city,print_district):widget.connect('toggled',update_preview)
 update_preview()
 weather_mode=combo([('auto','自动 · 网络天气'),('manual','手动设置天气')]);weather_mode.set_active_id(settings['weather_mode']);row('天气来源',weather_mode)
 condition=combo(WEATHER_CHOICES);condition.set_active_id(str(settings['code']));row('天气',condition)
 temperature=Gtk.SpinButton.new_with_range(-90,60,1);temperature.set_digits(1);temperature.set_numeric(True);temperature.set_value(settings['temperature']);row('温度（°C）',temperature)
 def sensitivity(*_):
  for w in (province,city,district,print_province,print_city,print_district):w.set_sensitive(city_mode.get_active_id()=='manual')
  for w in (condition,temperature):w.set_sensitive(weather_mode.get_active_id()=='manual')
 city_mode.connect('changed',sensitivity);weather_mode.connect('changed',sensitivity);sensitivity()
 note=Gtk.Label(label='IP 定位按网络出口确定城市；自动城市和天气每 10 分钟更新，超过 3 小时或跨天失效。手动天气一直保留。',xalign=0);note.set_line_wrap(True);note.set_max_width_chars(27);body.pack_start(note,False,False,0)
 status=Gtk.Label(xalign=0);status.set_line_wrap(True);status.set_max_width_chars(27);body.pack_start(status,False,False,0)
 saved=Gtk.Label(xalign=0);saved.set_line_wrap(True);saved.set_max_width_chars(27);body.pack_start(saved,False,False,0)
 def apply(*_):
  try:
   value=dict(city_mode=city_mode.get_active_id(),weather_mode=weather_mode.get_active_id(),province=current_province()['name'],city=current_city()['name'],district='' if not district.get_active_id() else district.get_active_text(),temperature=temperature.get_value(),code=int(condition.get_active_id()),print_province=print_province.get_active(),print_city=print_city.get_active(),print_district=print_district.get_active())
   save(path,value)
   if p.festival:p.festival.weather.refresh()
   saved.set_text('已保存，下一张报纸使用新设置。')
  except (ValueError,OSError) as error:saved.set_text('保存失败：'+str(error))
 button=Gtk.Button(label='保存城市与天气 · 立即更新');button.connect('clicked',apply);body.pack_start(button,False,False,0)
 def update():
  if not p.running:return False
  weather=getattr(getattr(p,'festival',None),'weather',None)
  status.set_text(('当前报纸：'+weather_label(weather.snapshot())+'\n'+weather.status) if weather else '天气模块正在初始化…');return True
 GLib.timeout_add_seconds(2,update);update()
 return dict(city_mode=city_mode,weather_mode=weather_mode,province=province,city=city,district=district,temperature=temperature,condition=condition,save=button,status=status,print_province=print_province,print_city=print_city,print_district=print_district,preview=preview)
