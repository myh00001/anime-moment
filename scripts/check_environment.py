from pathlib import Path
import sys,platform,json,hashlib,importlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'service/vendor'))

def main():
    errors = []
    print('System:', platform.system(), platform.machine(), platform.python_version())
    if platform.system() != 'Linux' or platform.machine() not in ('aarch64','arm64'):
        errors.append('S100 Linux aarch64 is required for HBM execution')
    for name in ['numpy','cv2','PIL','hbm_runtime','gi','cairo']:
        try:
            module = importlib.import_module(name)
            print('Available:', name, getattr(module, '__version__','system'))
        except ImportError as exc:
            errors.append(f'{name}: {exc}')
    for item in json.loads((ROOT/'models-manifest.json').read_text(encoding='utf-8'))['models']:
        path = ROOT/'service/models'/item['file']
        if not path.is_file():
            errors.append('Missing model: '+item['file'])
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            errors.append('Model checksum mismatch: '+item['file'])
        else:
            print('Model verified:', item['file'])
    devices = sorted(str(p) for p in Path('/dev/v4l/by-id').glob('*video-index0'))
    print('USB camera nodes:', devices or 'not found; application will wait for connection')
    for error in errors:
        print('ERROR:', error)
    if errors:
        raise SystemExit(1)
    print('Environment checks passed; run the player to verify actual inference and display.')

if __name__ == '__main__':
    main()
