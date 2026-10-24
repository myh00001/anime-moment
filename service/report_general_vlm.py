"""Resident, serialized local InternVL image observation runtime."""
from pathlib import Path
import atexit
import base64
import io
import json
import os
import select
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

PROMPT = ('你是校园科技节纪念报纸的中文编辑。活动主题：做中学科学，实践促创新。'
          'AI动漫拍报机让影像变成科技节纪念。请根据提供的画面观察写两句短报道：'
          '第一句客观叙述观察事实，第二句联系AI影像和科技节纪念意义。'
          '不要重复校名、年份和主题，不要标题。不得补充观察里没有的人物身份、物品、背景或动作，'
          '不写心理推测，不说已经打印、获奖或采访。只输出正文。')
OBSERVATION = '用一句简短中文描述照片里最明显的可见事实。有人则描述身体朝向、手的位置或明显表情，无人则描述主要环境。不猜身份或具体手势含义，不猜遮挡部分。'


class VisionRuntime:
    def __init__(self, root=None, binary=None, threads=6, bpu=False, ffn_config=None):
        self.root = Path(root or Path(__file__).resolve().parent)
        prepared=self.root/'local-vlm/build-general-report'
        default=(prepared/'bin/llama-server' if (prepared/'.bridge-ready').is_file()
                 else self.root/'local-vlm/build/bin/llama-server')
        self.binary = Path(binary or os.environ.get('FESTIVAL_GENERAL_VLM_BINARY',str(default)))
        self.model_size=os.environ.get('FESTIVAL_GENERAL_VLM_SIZE','2B')
        if self.model_size not in ('1B','2B'):raise ValueError('Unsupported general VLM size')
        self.bpu=bpu and self.model_size=='2B'
        self.model_name='InternVL3-'+self.model_size+'-Instruct-Q8_0'
        self.cpu_binary=self.binary
        self.ffn=None
        if self.model_size=='2B' and bpu:
            from report_ffn import load_config,Sidecar
            try:
                config=ffn_config
                if config is None and binary is None and not os.environ.get('FESTIVAL_GENERAL_VLM_BINARY'):
                    config=load_config(self.root)
                if config is not None:
                    self.ffn=Sidecar(self.root,config);self.binary=config['binary']
            except (OSError,ValueError,KeyError,TypeError):
                self.ffn=None
        self.worker = None
        self.result_fd = None
        self.result_buffer = b''
        self.sequence = 0
        self.shutdown_requested = threading.Event()
        self.threads = threads
        self.owner = os.getpid()
        self.lock = threading.RLock()
        self.process = None
        self.folder = None
        self.log = None
        self.startup_seconds = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        atexit.register(self.shutdown)

    def warm(self):
        with self.lock:
            if self.shutdown_requested.is_set():raise RuntimeError('Vision runtime is shutting down')
            if self.process is not None and self.process.poll() is None:
                return
            self.close()
            started = time.monotonic()
            self.folder = tempfile.TemporaryDirectory(prefix='general-vlm-')
            self.log = (Path(self.folder.name)/'runtime.log').open('w+')
            embedding=Path(self.folder.name)/'embedding.bin'
            self.embedding=embedding
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
            self.endpoint = f'http://127.0.0.1:{port}'
            model = self.root/'local-vlm/internvl2b-candidate'
            language=model/'language.gguf' if self.model_size=='2B' else self.root/'local-vlm/InternVL3-1B-Instruct-Q8_0.gguf'
            projector=model/'mmproj.gguf' if self.model_size=='2B' else self.root/'local-vlm/mmproj-InternVL3-1B-Instruct-Q8_0.gguf'
            if self.bpu and (not (model/'vision.hbm').is_file() or not self.binary.is_file() or b'S100 embedding accepted' not in self.binary.read_bytes()):self.bpu=False
            command = [str(self.binary),'--model',str(language),
                       '--mmproj',str(projector),'--host','127.0.0.1','--port',str(port),
                       '--threads',str(self.threads),'--threads-batch',str(self.threads),
                       '--ctx-size','2048','--cache-ram','0','--parallel','1','--n-gpu-layers','0',
                       '--jinja','--no-webui','--image-max-tokens','256']
            command += ['--no-mmproj-offload']
            env = {key:value for key,value in os.environ.items() if key!='S100_VLM_EMBED_FILE'}
            env['OPENBLAS_NUM_THREADS'] = str(self.threads)
            env.update(OMP_NUM_THREADS=str(self.threads),OMP_DYNAMIC='FALSE')
            if self.bpu:env['S100_VLM_EMBED_FILE']=str(embedding)
            try:
                if self.ffn is not None:self.ffn.environment(env)
                self.process = subprocess.Popen(command,stdout=self.log,stderr=subprocess.STDOUT,env=env)
                deadline = started+80
                while time.monotonic()<deadline:
                    if self.shutdown_requested.is_set():raise RuntimeError('Vision runtime is shutting down')
                    if self.process.poll() is not None:
                        raise RuntimeError('General VLM startup failed')
                    try:
                        with self.opener.open(self.endpoint+'/health',timeout=.5) as response:
                            if response.status==200:
                                self.startup_seconds=time.monotonic()-started
                                return
                    except OSError: pass
                    time.sleep(.1)
                raise TimeoutError('General VLM warmup timed out')
            except Exception:
                self.close()
                raise

    def generate(self, photo):
        from PIL import Image
        with self.lock:
            started=time.monotonic()
            self.warm()
            ready=time.monotonic()
            if self.ffn is not None:self.ffn.start()
            ffn_since=self.ffn.counter() if self.ffn is not None else 0
            with Image.open(photo) as source:
                image=source.convert('RGB')
                if self.bpu:image=image.resize((448,448),Image.Resampling.BICUBIC)
                else:image.thumbnail((448,448),Image.Resampling.LANCZOS)
                buffer=io.BytesIO(); image.save(buffer,format='JPEG',quality=92)
            encoder_seconds=0
            encoder_pre_ffn_release_seconds=0
            self.encoder_load_seconds=0
            if self.bpu:
                try:
                    self.sequence+=1
                    if self.ffn is not None:
                        event=self.ffn.encode(photo,self.embedding,self.sequence)
                        self.encoder_load_seconds=event['load_seconds']
                    else:
                        self.warm_encoder()
                        self.worker.stdin.write((json.dumps({'photo':str(photo),'sequence':self.sequence})+'\n').encode())
                        self.worker.stdin.flush()
                        event=self.read_event(5)
                        self.worker.stdin.close()
                        self.worker.stdin=None
                    if event.get('sequence')!=self.sequence or event.get('state')!='encoded':
                        raise RuntimeError('Image embedding sequence mismatch')
                    encoder_seconds=event['seconds']
                except Exception:
                    self.close()
                    raise
            payload={'messages':[{'role':'system','content':'只描述照片中直接可见的事实，不猜测身份和遮挡部位。'},
                     {'role':'user','content':[
                       {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()}},
                       {'type':'text','text':OBSERVATION}]}],
                     'temperature':0,'max_tokens':120,'cache_prompt':False,'stream':False,
                     'grammar':'root ::= [一-鿿] [一-鿿，。！？、：；A-Za-z0-9 ]{8,32}'}
            request=urllib.request.Request(self.endpoint+'/v1/chat/completions',data=json.dumps(payload).encode(),
                                           headers={'Content-Type':'application/json'})
            http_started=time.monotonic()
            ffn_profile=None
            try:
                with self.opener.open(request,timeout=32) as response:
                    data=json.load(response)
                http_seconds=time.monotonic()-http_started
                if self.ffn is not None:ffn_profile=self.ffn.finish(ffn_since)
            except Exception:
                self.close()
                raise
            cleanup_started=time.monotonic()
            if self.bpu:self.close_encoder()
            cleanup_seconds=time.monotonic()-cleanup_started
            text=data['choices'][0]['message']['content']
            return {'text':text,'observation':text,'seconds':round(time.monotonic()-started,3),
                    'inference_seconds':round(time.monotonic()-ready,3),
                    'startup_seconds':round(self.startup_seconds,3),
                    'encoder_pre_ffn_release_seconds':encoder_pre_ffn_release_seconds,
                    'encoder_load_seconds':getattr(self,'encoder_load_seconds',0),'encoder_cleanup_seconds':round(cleanup_seconds,3),'http_seconds':round(http_seconds,3),'encoder_seconds':encoder_seconds,'feature_sha':event['feature_sha'] if self.bpu else None,
                    'timings':data.get('timings',{}),'model':self.model_name,'ffn_profile':ffn_profile,
                    'backend':('InternVL3 general VLM: BPU vision + BPU FFN prefill / CPU decode + Qwen3 writing' if self.bpu and ffn_profile else 'InternVL3 general VLM: BPU vision + Qwen3 writing' if self.bpu
                               else 'InternVL3 general VLM: CPU vision + Qwen3 writing')}

    def warm_encoder(self):
        loading_started=time.monotonic()
        embedding=Path(self.folder.name)/'embedding.bin'
        read_fd,write_fd=os.pipe()
        self.result_fd=read_fd
        try:
            self.worker=subprocess.Popen(
                ['python3',str(self.root/'report_vision_worker.py'),
                 '--root',str(self.root),'--embedding',str(embedding),'--fd',str(write_fd)],
                stdin=subprocess.PIPE,stdout=self.log,stderr=subprocess.STDOUT,
                pass_fds=(write_fd,))
        except Exception:
            self.close()
            raise
        finally:os.close(write_fd)
        try:
            if self.read_event(12).get('state')!='ready':raise RuntimeError('BPU worker did not initialize')
            self.encoder_load_seconds=round(time.monotonic()-loading_started,3)
        except Exception:
            self.close()
            raise


    def close_encoder(self):
        if self.worker is not None:
            if self.worker.stdin is not None:self.worker.stdin.close()
            try:self.worker.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.worker.kill();self.worker.wait()
            self.worker=None
        if self.result_fd is not None:
            os.close(self.result_fd);self.result_fd=None
        self.result_buffer=b''

    def read_event(self,timeout):
        deadline=time.monotonic()+timeout
        while b'\n' not in self.result_buffer:
            if self.shutdown_requested.is_set():raise RuntimeError('Vision runtime is shutting down')
            left=deadline-time.monotonic()
            if left<=0:
                raise TimeoutError('BPU image worker timed out')
            if not select.select([self.result_fd],[],[],min(.25,left))[0]:continue
            data=os.read(self.result_fd,4096)
            if not data:raise RuntimeError('BPU image worker exited')
            self.result_buffer+=data
        line,self.result_buffer=self.result_buffer.split(b'\n',1)
        return json.loads(line)

    def close(self):
        if os.getpid()!=self.owner: return
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=3)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
            self.process=None
            if self.ffn is not None:self.ffn.close()
            self.close_encoder()
            if self.log is not None: self.log.close(); self.log=None
            if self.folder is not None: self.folder.cleanup(); self.folder=None

    def shutdown(self):
        if os.getpid()!=self.owner:return
        self.shutdown_requested.set()
        # Cancel a pending HTTP request before waiting for the serialization lock.
        if self.process is not None and self.process.poll() is None:self.process.terminate()
        self.close()


_runtime = None
_guard = threading.Lock()


def runtime():
    global _runtime
    with _guard:
        if _runtime is None or _runtime.owner!=os.getpid(): _runtime=VisionRuntime(bpu=True)
        return _runtime


def warm():
    runtime().warm()


def generate(photo):
    engine=runtime()
    used_ffn=engine.ffn is not None
    try:return engine.generate(photo)
    except Exception as error:
        if engine.shutdown_requested.is_set():raise
        if used_ffn:
            engine.close();engine.ffn=None;engine.binary=engine.cpu_binary
            result=engine.generate(photo)
            result['acceleration_fallback']='FFN-'+type(error).__name__
            return result
        if not engine.bpu:raise
        engine.close();engine.bpu=False
        result=engine.generate(photo)
        result['acceleration_fallback']=type(error).__name__
        return result


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor'))
    print('GENERAL_VLM_RESULT='+json.dumps(generate(sys.argv[1]),ensure_ascii=True),flush=True)
