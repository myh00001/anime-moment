"""Pin an already-built FFN experiment; do not enable it without --enable.

This helper neither downloads models nor restarts the camera. All artifacts must
already have been built from the installed InternVL3-2B Q8 weights and validated.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):value.update(block)
    return value.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--layers',default=','.join(map(str,range(27))))
    parser.add_argument('--enable',action='store_true')
    args=parser.parse_args()
    root=args.root.resolve();local=root/'local-vlm'
    layers=sorted(set(int(value) for value in args.layers.split(',')))
    if not layers or any(not 0<=value<27 for value in layers):raise ValueError('Expected FFN layers 0..26')
    binary=local/'ffn-bridge-runtime/bin/llama-server';models=local/'language-bpu-step1/ffn-models'
    if b'S100_FFN_USED' not in binary.read_bytes():raise ValueError('FFN bridge binary is missing')
    paths={'language_sha256':local/'internvl2b-candidate/language.gguf','binary_sha256':binary}
    model_hashes={str(layer):{'sha256':digest(models/f'ffn{layer}_t256.hbm')} for layer in layers}
    worker=root/'report_ffn_worker.py'
    shutil.copy2(Path(__file__).with_name('ffn_bridge_worker.py'),worker)
    paths['worker_sha256']=worker
    config={'version':1,'enabled':True,'binary':str(binary.relative_to(local)),
            'models_directory':str(models.relative_to(local)),'models':model_hashes,
            **{key:digest(path) for key,path in paths.items()}}
    target=local/('report-ffn.json' if args.enable else 'report-ffn-candidate.json')
    temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(config,indent=2));temporary.replace(target)
    print(('Enabled' if args.enable else 'Candidate only')+': '+str(target))


if __name__=='__main__':main()
