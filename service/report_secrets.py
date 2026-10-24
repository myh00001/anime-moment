"""Device-local API credential storage, separate from capture/settings records."""
import json
import os
from pathlib import Path
import tempfile


def validate_key(value):
    if not isinstance(value,str):raise ValueError('API Key 无效')
    value=value.strip()
    if len(value)>4096 or any(not 33<=ord(char)<=126 for char in value):
        raise ValueError('API Key 不能包含空格、换行或非英文字符')
    return value


def load_key(root):
    try:
        data=json.loads((Path(root)/'report-secrets.json').read_text(encoding='utf-8'))
        return validate_key(data.get('deepseek_api_key',''))
    except (OSError,ValueError,TypeError,AttributeError):return ''


def save_key(root,value):
    value=validate_key(value);root=Path(root)
    descriptor,name=tempfile.mkstemp(prefix='.report-secrets-',suffix='.tmp',dir=root)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump({'deepseek_api_key':value},stream)
            stream.flush();os.fsync(stream.fileno())
        os.chmod(name,0o600);os.replace(name,root/'report-secrets.json')
    finally:
        if os.path.exists(name):os.unlink(name)
