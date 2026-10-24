"""Experimental S100 FFN sidecar. Private Unix socket, opt-in models only."""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time

MAGIC=0x5346464e


def receive(connection,length):
    result=bytearray()
    while len(result)<length:
        block=connection.recv(length-len(result))
        if not block:raise EOFError('Incomplete FFN packet')
        result.extend(block)
    return result


def serve(root,models_path,socket_path,metrics):
    os.environ['OPENBLAS_NUM_THREADS']='1'
    sys.path[:0]=[str(root),str(root/'vendor')]
    import numpy as np
    from hbm_runner import HbmRunner
    models={};stats=deque(maxlen=256);counter=0
    os.umask(0o077)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(str(socket_path));server.listen(1)
        print('FFN_WORKER_READY',flush=True)
        while True:
            connection,_=server.accept()
            with connection:
                connection.settimeout(15)
                magic,layer,channels,tokens=struct.unpack('<IIII',receive(connection,16))
                if magic==MAGIC and layer==0xfffffffe and channels==0 and 0<tokens<=8192:
                    from PIL import Image
                    from report_vision_worker import write_embedding
                    request=json.loads(receive(connection,tokens))
                    loaded=time.perf_counter()
                    if 'encoder' not in models:
                        models['encoder']=HbmRunner(root/'local-vlm/internvl2b-candidate/vision.hbm')
                    load_seconds=time.perf_counter()-loaded
                    started=time.perf_counter()
                    with Image.open(request['photo']) as source:
                        image=source.convert('RGB').resize((448,448),Image.Resampling.BICUBIC)
                    pixels=np.asarray(image,dtype=np.float32)/255
                    pixels=(pixels-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
                    features=models['encoder'](pixels.transpose(2,0,1)[None])[0]
                    details=write_embedding(features,request['embedding'])
                    event={'state':'encoded','sequence':request['sequence'],
                           'seconds':round(time.perf_counter()-started,4),
                           'load_seconds':round(load_seconds,4),**details}
                    payload=json.dumps(event).encode()
                    connection.sendall(struct.pack('<IIIII',magic,layer,0,len(payload),0)+payload)
                    continue
                if magic!=MAGIC or not 0<=layer<27 or channels!=1536 or not 128<=tokens<=256:
                    raise ValueError('Invalid FFN header')
                hidden=np.frombuffer(receive(connection,tokens*channels*4),'<f4').reshape(tokens,channels)
                if not np.isfinite(hidden).all():raise ValueError('Nonfinite FFN input')
                started=time.perf_counter()
                if layer not in models:
                    models[layer]=HbmRunner(models_path/f'ffn{layer}_t256.hbm')
                    if models[layer].shape!=(1,1536,1,256):raise ValueError('Unsupported FFN model shape')
                padded=np.zeros((1,channels,1,256),np.float32)
                padded[0,:,0,:tokens]=hidden.T
                result=models[layer](padded)[0][0,:,0,:tokens].T.copy()
                if result.shape!=hidden.shape or not np.isfinite(result).all():raise ValueError('Invalid FFN output')
                connection.sendall(struct.pack('<IIIII',magic,layer,channels,tokens,0))
                connection.sendall(result.tobytes())
                counter+=1
                stats.append({'index':counter,'layer':layer,'tokens':tokens,'seconds':time.perf_counter()-started})
                temporary=metrics.with_suffix('.tmp')
                temporary.write_text(json.dumps(list(stats)))
                temporary.replace(metrics)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--models',type=Path,required=True)
    parser.add_argument('--socket',type=Path,required=True)
    parser.add_argument('--metrics',type=Path)
    args=parser.parse_args()
    serve(args.root,args.models,args.socket,args.metrics or args.models/'last-ffn-worker-stats.json')


if __name__=='__main__':main()
