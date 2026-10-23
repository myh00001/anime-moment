import sys,unittest
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from festival_weather import weather_label

class WeatherLabelTests(unittest.TestCase):
 def test_current_weather_has_city_description_and_temperature(self):
  now=datetime(2026,10,23,15,30,tzinfo=ZoneInfo('Asia/Shanghai'))
  value={'observed':'2026-10-23T15:15','temperature':18.4,'code':2}
  self.assertEqual(weather_label(value,now),'北京 多云 18°C')
 def test_missing_stale_or_future_weather_is_not_presented_as_current(self):
  now=datetime(2026,10,23,15,30,tzinfo=ZoneInfo('Asia/Shanghai'))
  for value in [None,{}, {'observed':'2026-10-22T15:00','temperature':18,'code':0},{'observed':'2026-10-23T18:00','temperature':18,'code':0},{'observed':'2026-10-23T15:00','temperature':float('nan'),'code':0}]:
   self.assertEqual(weather_label(value,now),'北京 天气暂不可用')
