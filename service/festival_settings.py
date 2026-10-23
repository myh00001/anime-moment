"""Persistent photo-wall and print options, separate from inference settings."""
import json
import re
import subprocess
from pathlib import Path

DEFAULT_OPTIONS = {'gallery_count': 0, 'print_enabled': True, 'printer': 'S100_Festival'}

def normalize_options(value):
    count = value.get('gallery_count', 0)
    enabled = value.get('print_enabled', True)
    printer = value.get('printer', 'S100_Festival')
    if type(count) is not int or not 0 <= count <= 20: raise ValueError('照片数量应为0至20')
    if type(enabled) is not bool: raise ValueError('打印开关无效')
    if not isinstance(printer, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,127}', printer): raise ValueError('打印机名称无效')
    return {'gallery_count': count, 'print_enabled': enabled, 'printer': printer}

def load_options(path):
    try: return normalize_options(json.loads(Path(path).read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError, AttributeError): return dict(DEFAULT_OPTIONS)

def save_options(path, value):
    value = normalize_options(value)
    path = Path(path)
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
    return value

def list_printers():
    import os
    try:
        result = subprocess.run(['lpstat', '-p'], env=dict(os.environ, LC_ALL='C'), capture_output=True, text=True, timeout=5)
        return sorted(set(re.findall(r'^printer\s+(\S+)', result.stdout, re.M)))
    except (OSError, subprocess.TimeoutExpired): return []

def wall_geometry(width, height, requested=0, aspect=16/9):
    """All rows fit; width follows row count, while leaving room for live video."""
    width, height = max(1, int(width)), max(1, int(height))
    aspect = max(.2, min(5., float(aspect)))
    gap = min(8, max(0, height//40))
    if requested:
        count = min(max(1, int(requested)), max(1, height//24))
        row_height = max(1, (height-gap*(count-1))//count)
        column_width = min(max(1, int(row_height*aspect)), max(1, int(width*.45)))
    else:
        column_width = min(235, max(1, int(width*.25)))
        row_height = max(1, int(column_width/aspect))
        count = min(20, max(1, (height+gap)//(row_height+gap)))
        row_height = min(row_height, max(1, (height-gap*(count-1))//count))
    return {'width': column_width, 'count': count, 'row_height': row_height, 'gap': gap}
