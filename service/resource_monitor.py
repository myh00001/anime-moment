"""Read-only Linux resource counters; unavailable sensors remain explicit."""
from pathlib import Path
import time

def corner_action(x,y,width,height,panel_visible=False,panel_width=480,panel_height=300):
 return {'hide_cursor':x>=width-80 and y>=height-80,
         'show_panel':(x<=80 and y<=80) or (panel_visible and x<=panel_width and y<=panel_height)}

class ResourceMonitor:
 def __init__(self):self.previous=None
 def sample(self):
  result={'time':time.time()}
  try:result['bpu_frequency_mhz']=int(Path('/sys/class/devfreq/28108000.bpu/cur_freq').read_text())/1000000
  except (OSError,ValueError):pass
  try:
   values=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]));total=sum(values);idle=values[3]+values[4]
   if self.previous:
    dt=total-self.previous[0];result['cpu_percent']=max(0,min(100,100*(1-(idle-self.previous[1])/dt))) if dt else 0
   self.previous=(total,idle)
  except (OSError,ValueError):pass
  try:
   mem={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
   result['memory_used_gb']=(mem['MemTotal']-mem['MemAvailable'])/1048576;result['memory_total_gb']=mem['MemTotal']/1048576
  except (OSError,ValueError,KeyError):pass
  result['bpu_percent']={}
  for p in Path('/sys/devices/system/bpu').glob('bpu*/ratio'):
   try:result['bpu_percent'][p.parent.name]=float(p.read_text().strip())
   except (OSError,ValueError):pass
  result['temperatures']={}
  for p in Path('/sys/class/thermal').glob('thermal_zone*'):
   try:result['temperatures'][(p/'type').read_text().strip()]=float((p/'temp').read_text())/1000
   except (OSError,ValueError):pass
  return result
