"""Verify every source model before copying any files into the application."""
from pathlib import Path
import argparse,hashlib,json,shutil

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    models = json.loads((ROOT/'models-manifest.json').read_text(encoding='utf-8'))['models']
    for item in models:
        source = args.source/item['file']
        if not source.is_file() or digest(source) != item['sha256']:
            raise SystemExit(f"Missing or mismatched model: {item['file']}; no files copied")
    destination = ROOT/'service/models'
    destination.mkdir(exist_ok=True)
    for item in models:
        source = (args.source/item['file']).resolve()
        target = destination/item['file']
        if source != target.resolve():
            pending = target.with_suffix(target.suffix+'.importing')
            shutil.copyfile(source, pending)
            pending.replace(target)
        print('Verified:', item['file'])

if __name__ == '__main__':
    main()
