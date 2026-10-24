"""Persistent BPU image encoder; result events use a dedicated private pipe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time


def write_embedding(features,path):
    import numpy as np
    features=np.asarray(features,dtype=np.float32)
    if features.shape!=(1,256,1536) or not np.isfinite(features).all() or float(features.std())<1e-8:
        raise ValueError('Invalid InternVL3-2B BPU features')
    path=Path(path)
    temporary=path.with_suffix('.tmp')
    temporary.write_bytes(struct.pack('<III',0x53313030,256,1536)+np.asarray(features,dtype='<f4').tobytes())
    temporary.replace(path)
    return {'feature_sha':hashlib.sha256(features.tobytes()).hexdigest(),
            'feature_mean':float(features.mean()),'feature_std':float(features.std())}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    parser.add_argument('--embedding',required=True)
    parser.add_argument('--fd',type=int,required=True)
    args=parser.parse_args()
    root=Path(args.root)
    sys.path[:0]=[str(root),str(root/'vendor')]
    import numpy as np
    from PIL import Image
    from hbm_runner import HbmRunner

    def event(value):
        data=(json.dumps(value)+'\n').encode()
        while data:
            written=os.write(args.fd,data)
            data=data[written:]

    encoder=HbmRunner(root/'local-vlm/internvl2b-candidate/vision.hbm')
    event({'state':'ready'})
    for line in sys.stdin:
        request=json.loads(line)
        started=time.monotonic()
        with Image.open(request['photo']) as source:
            image=source.convert('RGB').resize((448,448),Image.Resampling.BICUBIC)
        pixels=np.asarray(image,dtype=np.float32)/255
        pixels=(pixels-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
        features=encoder(pixels.transpose(2,0,1)[None])[0]
        details=write_embedding(features,args.embedding)
        event({'state':'encoded','sequence':request['sequence'],
               'seconds':round(time.monotonic()-started,4),
               **details})


if __name__=='__main__':main()
