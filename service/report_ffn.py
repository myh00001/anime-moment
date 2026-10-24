"""Optional, hash-pinned experimental FFN sidecar. Disabled without a manifest."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import tempfile
import time

_hashes={}


def verify(path,expected):
    if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Invalid artifact digest')
    stat=path.stat();key=(str(path),stat.st_size,stat.st_mtime_ns)
    if key not in _hashes:
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
        _hashes[key]=digest.hexdigest()
    if _hashes[key]!=expected:raise ValueError('FFN artifact does not match manifest')


def load_config(root,manifest=None):
    root=Path(root).resolve();local=root/'local-vlm'
    path=Path(manifest).resolve() if manifest is not None else local/'report-ffn.json'
    if local not in path.parents:raise ValueError('FFN manifest is outside model directory')
    if os.environ.get('FESTIVAL_GENERAL_VLM_NO_FFN')=='1' or not path.exists():return None
    config=json.loads(path.read_text())
    if config.get('enabled') is not True:return None
    if config.get('version')!=1:raise ValueError('Unsupported FFN manifest')
    def inside(relative):
        value=(local/relative).resolve()
        if local not in value.parents:raise ValueError('FFN path is outside model directory')
        return value
    binary=inside(config['binary']);models=inside(config['models_directory'])
    language=local/'internvl2b-candidate/language.gguf';worker=root/'report_ffn_worker.py'
    verify(language,config['language_sha256']);verify(binary,config['binary_sha256']);verify(worker,config['worker_sha256'])
    layers=sorted(int(value) for value in config['models'])
    if not layers or len(layers)>27 or any(not 0<=value<27 for value in layers):raise ValueError('Invalid FFN layers')
    if len(set(layers))!=len(layers):raise ValueError('Duplicate FFN layers')
    for layer in layers:verify(models/f'ffn{layer}_t256.hbm',config['models'][str(layer)]['sha256'])
    return {'binary':binary,'models':models,'worker':worker,'layers':layers}


class Sidecar:
    def __init__(self,root,config):
        self.root=Path(root);self.config=config;self.owner=os.getpid()
        self.process=None;self.folder=None;self.log=None;self.releasing=False

    def start(self):
        if os.getpid()!=self.owner:raise RuntimeError('FFN sidecar belongs to another process')
        if self.process is not None and self.process.poll() is None and not self.releasing:return
        self.stop_worker()
        if self.folder is None:self.folder=tempfile.TemporaryDirectory(prefix='report-ffn-')
        directory=Path(self.folder.name);self.socket=directory/'worker.sock';self.metrics=directory/'metrics.json'
        self.socket.unlink(missing_ok=True);self.metrics.unlink(missing_ok=True)
        self.log=(directory/'worker.log').open('w')
        self.process=subprocess.Popen(['python3',str(self.config['worker']),'--root',str(self.root),
            '--models',str(self.config['models']),'--socket',str(self.socket),'--metrics',str(self.metrics)],
            stdout=self.log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+10
        while not self.socket.exists():
            if self.process.poll() is not None or time.monotonic()>deadline:
                self.close();raise RuntimeError('FFN sidecar startup failed')
            time.sleep(.02)

    def environment(self,environment):
        self.start()
        environment['S100_FFN_SOCKET']=str(self.socket)
        environment['S100_FFN_LAYERS']=','.join(map(str,self.config['layers']))

    def encode(self,photo,embedding,sequence):
        payload=json.dumps({'photo':str(photo),'embedding':str(embedding),'sequence':sequence}).encode()
        if len(payload)>8192:raise ValueError('Encoder request is too large')
        def receive(connection,length):
            packet=bytearray()
            while len(packet)<length:
                block=connection.recv(length-len(packet))
                if not block:raise EOFError('Incomplete encoder response')
                packet.extend(block)
            return packet
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.settimeout(15);connection.connect(str(self.socket))
            connection.sendall(struct.pack('<IIII',0x5346464e,0xfffffffe,0,len(payload))+payload)
            magic,operation,channels,length,status=struct.unpack('<IIIII',receive(connection,20))
            if (magic,operation,channels,status)!=(0x5346464e,0xfffffffe,0,0) or not 0<length<=65536:
                raise ValueError('Invalid encoder response')
            event=json.loads(receive(connection,length))
            if event.get('state')!='encoded' or event.get('sequence')!=sequence:
                raise ValueError('Encoder sequence mismatch')
            return event

    def stats(self):
        if not hasattr(self,'metrics') or not self.metrics.exists():return []
        return json.loads(self.metrics.read_text())

    def counter(self):
        rows=self.stats();return rows[-1]['index'] if rows else 0

    def finish(self,since):
        rows=[row for row in self.stats() if row['index']>since]
        layers=sorted({row['layer'] for row in rows})
        if layers!=self.config['layers']:raise RuntimeError('Expected FFN BPU layers did not execute')
        # Vendor model handles must not survive into the next image encoder.
        # Release the complete process rather than recycle native contexts.
        self.stop_worker(wait=False)
        return {'layers':layers,'calls':len(rows),'worker_seconds':round(sum(row['seconds'] for row in rows),3)}

    def stop_worker(self,wait=True):
        if os.getpid()!=self.owner:return
        if self.process is not None and self.process.poll() is None:
            if not self.releasing:self.process.terminate()
            self.releasing=True
            if not wait:return
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.process=None;self.releasing=False
        if self.log is not None:self.log.close();self.log=None

    def close(self):
        if os.getpid()!=self.owner:return
        self.stop_worker()
        if self.folder is not None:self.folder.cleanup();self.folder=None
