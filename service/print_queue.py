"""Cancel only the explicitly selected printer's outstanding CUPS jobs."""
import subprocess
from festival_settings import normalize_options

def clear_queue(printer,runner=subprocess.run):
 printer=normalize_options({'printer':printer})['printer']
 result=runner(['cancel','-a',printer],capture_output=True,text=True,timeout=15)
 if result.returncode:
  result=runner(['sudo','-n','cancel','-a',printer],capture_output=True,text=True,timeout=15)
 if result.returncode:raise RuntimeError(result.stderr.strip() or '无法取消打印任务')
 check=runner(['lpstat','-o',printer],capture_output=True,text=True,timeout=5)
 if check.returncode:raise RuntimeError(check.stderr.strip() or '无法确认打印队列状态')
 if check.stdout.strip():raise RuntimeError('仍有任务未取消，请稍后重试')


def queue_count(printer,runner=subprocess.run):
 printer=normalize_options({'printer':printer})['printer']
 result=runner(['lpstat','-o',printer],capture_output=True,text=True,timeout=5)
 if result.returncode:raise RuntimeError(result.stderr.strip() or '无法读取打印队列')
 return sum(bool(line.strip()) for line in result.stdout.splitlines())
