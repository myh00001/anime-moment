"""Cached Beijing weather; network requests never run in the photo/print path."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json,math,time,threading,urllib.request

URL='https://api.open-meteo.com/v1/forecast?latitude=39.928&longitude=116.416&current=temperature_2m,weather_code&timezone=Asia%2FShanghai'

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

def weather_label(value, now=None):
    now=now or datetime.now(ZoneInfo('Asia/Shanghai'))
    try:
        measured=datetime.fromisoformat(value['observed']).replace(tzinfo=ZoneInfo('Asia/Shanghai'))
        age=(now-measured).total_seconds();temperature=float(value['temperature'])
        if not 0<=age<=10800 or measured.date()!=now.date() or not math.isfinite(temperature):raise ValueError('Stale weather')
        return f"北京 {weather_description(int(value['code']))} {temperature:.0f}°C"
    except (TypeError,KeyError,ValueError,OverflowError):return '北京 天气暂不可用'

class WeatherCache:
    def __init__(self,path,running):
        self.path=Path(path);self.running=running;self.value=None
        try:self.value=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def snapshot(self):return dict(self.value) if isinstance(self.value,dict) else None
    def loop(self):
        next_update=0
        while self.running():
            if time.monotonic()>=next_update:
                try:
                    with urllib.request.urlopen(URL,timeout=5) as response:data=json.load(response)['current']
                    value={'observed':data['time'],'temperature':float(data['temperature_2m']),'code':int(data['weather_code']),'source':'Open-Meteo'}
                    self.value=value;temp=self.path.with_name(self.path.name+'.tmp');temp.write_text(json.dumps(value),encoding='utf-8');temp.replace(self.path)
                    next_update=time.monotonic()+1800
                except Exception:next_update=time.monotonic()+300
            time.sleep(1)
