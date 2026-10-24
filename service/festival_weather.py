"""IP location and weather run only in a background thread."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json,math,time,threading,urllib.request,urllib.parse
from weather_settings import load

UPDATE_SECONDS=600

def weather_description(code):
 if code==0:return '晴'
 if code in (1,2):return '多云'
 if code==3:return '阴'
 if code in (45,48):return '雾'
 if code in (51,53,55,56,57):return '毛毛雨'
 if code in (61,63,65,66,67,80,81,82):return '雨'
 if code in (71,73,75,77,85,86):return '雪'
 if code in (95,96,99):return '雷雨'
 return '天气数据'
def weather_valid(value,now=None):
 now=now or datetime.now(ZoneInfo('Asia/Shanghai'))
 try:
  if not math.isfinite(float(value['temperature'])):return False
  int(value['code'])
  if value.get('manual'):return True
  measured=datetime.fromisoformat(value['observed']).replace(tzinfo=ZoneInfo('Asia/Shanghai'))
  return 0<=(now-measured).total_seconds()<=10800 and measured.date()==now.date()
 except (TypeError,KeyError,ValueError,OverflowError):return False
def weather_label(value,now=None):
 city=(value or {}).get('city','北京')
 if weather_valid(value,now):return f"{city} {weather_description(int(value['code']))} {float(value['temperature']):.0f}°C"
 return city+' 天气暂不可用'
def fetch_json(url):
 request=urllib.request.Request(url,headers={'User-Agent':'AnimeMoment/1.0'})
 with urllib.request.urlopen(request,timeout=8) as response:return json.load(response)
MUNICIPALITIES=('北京市','天津市','上海市','重庆市')
PSEUDO_CITIES=('市辖区','县','省直辖县级行政区划','自治区直辖县级行政区划')
def print_place_name(name):
 for suffix in ('维吾尔自治区','壮族自治区','回族自治区','特别行政区','自治区','省','市','区'):
  if name.endswith(suffix):return name[:-len(suffix)]
 return name
def format_location(location,settings):
 province=location.get('province','');city=location.get('city','');district=location.get('district','')
 if city in PSEUDO_CITIES:city=province if province in MUNICIPALITIES else ''
 if province in MUNICIPALITIES:city=province
 if settings['city_mode']=='auto':parts=[city or province,district] if province in MUNICIPALITIES else [province,city]
 else:parts=[province if settings.get('print_province',True) else '',city if settings.get('print_city',True) else '',district if settings.get('print_district',True) else '']
 return ' '.join(dict.fromkeys(print_place_name(x) for x in parts if x))
def locate_ip(fetch=fetch_json):
 data=fetch('https://ipwho.is/?lang=zh-CN')
 if not data.get('success'):raise ValueError('IP 定位暂不可用')
 location=dict(province=data.get('region',''),city=data.get('city') or data.get('region') or '未知城市',district='',latitude=float(data['latitude']),longitude=float(data['longitude']))
 try:
  query=urllib.parse.urlencode(dict(latitude=location['latitude'],longitude=location['longitude'],localityLanguage='zh'))
  reverse=fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?'+query)
  location.update(province=reverse.get('principalSubdivision') or location['province'],city=reverse.get('city') or location['city'])
  admins=reverse.get('localityInfo',{}).get('administrative',[])
  # Chinese administrative codes avoid traditional/simplified name ambiguity.
  coded=[x.get('chinaAdminCode','').replace(' ','') for x in admins]
  code=next((x for x in reversed(coded) if len(x)==6),'')
  catalog=json.loads(Path(__file__).with_name('china-cities.json').read_text(encoding='utf-8-sig'))
  province=next((x for x in catalog if (code and x['code']==code[:2]) or x['name']==location['province']),None)
  if province:
   location['province']=province['name']
   city=next((x for x in province['children'] if code and x['code']==code[:4]),None)
   if city:
    location['city']=city['name'];district=next((x for x in city.get('children',[]) if x['code']==code),None)
    if district:location['district']=district['name']
  if not location['district']:
   district=reverse.get('locality','')
   if district.endswith(('区','區','县','縣')):location['district']=district
 except (OSError,ValueError,KeyError,TypeError):pass
 for name in MUNICIPALITIES:
  if location['province'].removesuffix('市')==name.removesuffix('市') or location['city'].removesuffix('市')==name.removesuffix('市'):location['province']=name;location['city']=name
 return location
def short_name(name):
 for suffix in ('维吾尔自治区','壮族自治区','回族自治区','特别行政区','自治区','自治州','地区','省','市','县','区','盟'):
  if name.endswith(suffix):return name[:-len(suffix)]
 return name
def locate_city(settings,fetch=fetch_json):
 city=settings['city'];province=settings['province'];district=settings['district']
 base=province if city in ('市辖区','县','省直辖县级行政区划','自治区直辖县级行政区划') else city
 queries=[]
 for name in ([district,base] if district else [base]):
  for query_name in dict.fromkeys([name,short_name(name)]):queries.append((name,query_name))
 for name,query_name in queries:
  query=urllib.parse.urlencode(dict(name=query_name,count=100,language='zh',format='json'))
  results=fetch('https://geocoding-api.open-meteo.com/v1/search?'+query).get('results',[])
  results=[r for r in results if r.get('country_code') in ('CN','TW','HK','MO')]
  region=short_name(province)
  matches=[r for r in results if region in r.get('admin1','') or region in r.get('name','')]
  if province=='台湾省':matches=[r for r in results if r.get('country_code')=='TW']
  if province=='香港特别行政区':matches=[r for r in results if r.get('country_code')=='HK']
  if province=='澳门特别行政区':matches=[r for r in results if r.get('country_code')=='MO']
  if not matches:continue
  exact=[r for r in matches if short_name(r['name'])==short_name(query_name)]
  if exact or matches:
   r=(exact or matches)[0]
   return dict(city=district or base,latitude=r['latitude'],longitude=r['longitude'])
 raise ValueError('未找到天气坐标，请选市级或手动天气')
class WeatherCache:
 def __init__(self,path,running):
  self.path=Path(path);self.settings_path=self.path.with_name('weather-settings.json');self.running=running;self.value=None;self.location=None;self.location_key=None;self.status='正在获取城市与天气';self.wake=threading.Event()
  try:self.value=json.loads(self.path.read_text(encoding='utf-8'))
  except (OSError,ValueError):pass
  self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
 def refresh(self):self.wake.set()
 @staticmethod
 def key(settings):return json.dumps(settings,sort_keys=True,ensure_ascii=False)
 def snapshot(self):
  settings=load(self.settings_path);key=self.key(settings)
  location=settings if settings['city_mode']=='manual' else (self.location or (self.value or {}).get('location') or dict(city='定位中'))
  city=format_location(location,settings)
  if settings['weather_mode']=='manual':return dict(city=city,temperature=settings['temperature'],code=settings['code'],manual=True,source='手动设置')
  if isinstance(self.value,dict) and self.value.get('settings_key')==key:return dict(self.value,city=city)
  return dict(city=city)
 def loop(self):
  next_update=0;last_key=None
  while self.running():
   settings=load(self.settings_path);key=self.key(settings)
   if key!=last_key or self.wake.is_set():next_update=0;last_key=key;self.wake.clear()
   if time.monotonic()>=next_update:
    try:
     location_key=(settings['city_mode'],settings['province'],settings['city'],settings['district'],settings['weather_mode'])
     if settings['city_mode']=='auto' or self.location_key!=location_key:
      self.location=locate_ip() if settings['city_mode']=='auto' else locate_city(settings) if settings['weather_mode']=='auto' else dict(city=settings['district'] or settings['city'])
      self.location_key=location_key
     if settings['weather_mode']=='auto':
      query=urllib.parse.urlencode(dict(latitude=self.location['latitude'],longitude=self.location['longitude'],current='temperature_2m,weather_code',timezone='Asia/Shanghai'))
      data=fetch_json('https://api.open-meteo.com/v1/forecast?'+query)['current']
      value=dict(city=format_location(settings if settings['city_mode']=='manual' else self.location,settings),location=self.location,observed=data['time'],temperature=float(data['temperature_2m']),code=int(data['weather_code']),source='Open-Meteo',settings_key=key)
      if key==self.key(load(self.settings_path)):
       self.value=value;temp=self.path.with_name(self.path.name+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temp.replace(self.path)
     self.status='已更新 · '+weather_label(self.snapshot());next_update=time.monotonic()+UPDATE_SECONDS
    except Exception as error:self.status='获取失败：'+str(error);next_update=time.monotonic()+300
   self.wake.wait(1)
