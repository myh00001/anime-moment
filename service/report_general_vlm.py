"""General InternVL observation from original pixels; no clothing classifier."""
from pathlib import Path
import base64
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

PROMPT = ('你是校园科技节纪念报纸的中文编辑。活动主题：做中学科学，实践促创新。'
          'AI动漫拍报机让影像变成科技节纪念。请根据提供的画面观察写两句短报道：'
          '第一句客观叙述观察事实，第二句联系AI影像和科技节纪念意义。'
          '不要重复校名、年份和主题，不要标题。不得补充观察里没有的人物身份、物品、背景或动作，'
          '不写心理推测，不说已经打印、获奖或采访。只输出正文。')


def generate(photo):
    from PIL import Image
    root = Path(__file__).resolve().parent
    use_two_b = os.environ.get('FESTIVAL_GENERAL_VLM_SIZE','2B') == '2B'
    language = root/'local-vlm/internvl2b-candidate/language.gguf' if use_two_b else root/'local-vlm/InternVL3-1B-Instruct-Q8_0.gguf'
    projector = root/'local-vlm/internvl2b-candidate/mmproj.gguf' if use_two_b else root/'local-vlm/mmproj-InternVL3-1B-Instruct-Q8_0.gguf'
    started = time.monotonic()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory(prefix='general-report-') as temporary:
        folder = Path(temporary)
        with Image.open(photo) as source:
            image = source.convert('RGB')
            image.thumbnail((448,448),Image.Resampling.LANCZOS)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        command = [str(root/'local-vlm/build/bin/llama-server'),
                   '--model',str(language),
                   '--mmproj',str(projector),
                   '--host','127.0.0.1','--port',str(port),'--threads','6','--threads-batch','6',
                   '--ctx-size','2048','--cache-ram','0','--parallel','1','--n-gpu-layers','0',
                   '--no-mmproj-offload','--jinja','--no-webui','--image-max-tokens','256']
        with (folder/'runtime.log').open('w+') as log:
            process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                                       env={key:value for key,value in os.environ.items() if key!='S100_VLM_EMBED_FILE'})
            try:
                deadline = started+30
                while time.monotonic() < deadline:
                    if process.poll() is not None: raise RuntimeError('General VLM startup failed')
                    try:
                        with opener.open(base+'/health',timeout=.5) as response:
                            if response.status == 200: break
                    except OSError: pass
                    time.sleep(.1)
                else: raise TimeoutError('General VLM startup timed out')
                buffer = io.BytesIO(); image.save(buffer,format='JPEG',quality=92)
                payload = {'messages':[{'role':'system','content':'只描述照片中直接可见的事实，不猜测身份和遮挡部位。'},{'role':'user','content':[
                    {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()}},
                    {'type':'text','text':'用一句简短中文描述照片里最明显的可见事实。有人则描述身体朝向、手的位置或明显表情，无人则描述主要环境。不猜身份或具体手势含义，不猜遮挡部分。'}]}], 'temperature':0,'max_tokens':120,
                    'grammar':'root ::= [一-鿿] [一-鿿，。！？、：；A-Za-z0-9 ]{8,32}',
                    'cache_prompt':False,'stream':False}
                request = urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(payload).encode(),
                                                  headers={'Content-Type':'application/json'})
                with opener.open(request,timeout=max(.1,deadline-time.monotonic())) as response:
                    result = json.load(response)
                observation = result['choices'][0]['message']['content']
                return {'text':observation,
                        'seconds':round(time.monotonic()-started,3),
                        'model':'InternVL3-2B-Instruct-Q8_0' if use_two_b else 'InternVL3-1B-Instruct-Q8_0','observation':observation,
                        'backend':'InternVL3 general VLM: CPU vision + Qwen3 writing'}
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor'))
    result = generate(sys.argv[1])
    print('GENERAL_VLM_RESULT='+json.dumps(result,ensure_ascii=True),flush=True)

