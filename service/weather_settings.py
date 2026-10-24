"""Persistent city/weather settings, separate from print configuration."""
import json,math
from pathlib import Path
DEFAULTS=dict(city_mode='auto',weather_mode='auto',province='北京市',city='北京市',district='',temperature=20.0,code=0,print_province=True,print_city=True,print_district=True)
WEATHER_CHOICES=[(0,'晴'),(2,'多云'),(3,'阴'),(45,'雾'),(51,'毛毛雨'),(61,'小雨'),(63,'中雨'),(65,'大雨'),(71,'小雪'),(73,'中雪'),(75,'大雪'),(95,'雷雨')]
def normalize(value):
 result=dict(DEFAULTS);result.update({k:v for k,v in value.items() if k in DEFAULTS})
 for k in ('city_mode','weather_mode'):
  if result[k] not in ('auto','manual'):raise ValueError('来源选项无效')
 for k in ('print_province','print_city','print_district'):
  if type(result[k]) is not bool:raise ValueError('打印地点选项无效')
 for k in ('province','city','district'):
  if not isinstance(result[k],str) or len(result[k])>60:raise ValueError('城市信息无效')
 if not result['city'].strip():raise ValueError('请选择城市')
 result['temperature']=float(result['temperature'])
 if not math.isfinite(result['temperature']) or not -90<=result['temperature']<=60:raise ValueError('温度应在 -90 至 60°C 之间')
 if result['code'] not in [x[0] for x in WEATHER_CHOICES]:raise ValueError('天气选项无效')
 return result
def load(path):
 try:return normalize(json.loads(Path(path).read_text(encoding='utf-8')))
 except (OSError,ValueError,TypeError,AttributeError):return dict(DEFAULTS)
def save(path,value):
 value=normalize(value);path=Path(path);temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path);return value
