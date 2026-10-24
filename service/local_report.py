"""Current local generative image reporting and parallel activity writing."""
import json
import os
import re
import subprocess
import time
import urllib.request

WRITER_ENDPOINT='http://127.0.0.1:8088'

def warm_local_model():
    env=dict(os.environ,XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}',
             DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{os.getuid()}/bus')
    subprocess.run(['systemctl','--user','start','anime-report-vlm.service'],
                   env=env,check=True,capture_output=True,timeout=6)


def warm_report_runtime():
    """Preload the language models without taking the BPU from the preview."""
    warm_local_model()
    from report_general_vlm import warm
    warm()


def clean_report(value):
    value=re.sub(r'<think>.*?</think>','',str(value),flags=re.S)
    value=re.sub(r'^(现场报道|报道正文|正文|画面观察)[：:]\s*','',value.strip())
    value=re.sub(r'\s+','',value).strip('“”"')
    value=re.sub(r'[*#`]+','',value)
    value=re.sub(r'[（(]\s*\d+\s*字\s*[）)]','',value)
    value=re.sub(r'。{2,}','。',value)
    if len(re.findall(r'[\u4e00-\u9fff]',value))<4:
        raise ValueError('模型未返回有效中文报道')
    if not any(word in value for word in ('AI','人工智能','科技节')):
        if value[-1] not in '。！？':value+='。'
        value+='AI动漫拍照让这一刻成为科技节的专属纪念。'
    if len(value)>96:
        value=value[:95].rstrip('，、；：。！？')+'。'
    elif value[-1] not in '。！？':value=value[:95].rstrip('，、；：')+'。'
    return value


class ReportWriter:
    def __init__(self):
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def complete(self,endpoint,payload,deadline):
        request=urllib.request.Request(endpoint+'/v1/chat/completions',
            data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type':'application/json'})
        left=deadline-time.monotonic()
        if left<=0:raise TimeoutError('本地报道生成超时')
        with self.opener.open(request,timeout=left) as response:
            result=json.load(response)
        return result['choices'][0]['message']['content']


def report_fact_sentence(value):
    value=re.sub(r'\s+','',str(value)).strip('“”"')
    finished=value.endswith(('。','！','？'))
    if '。' in value:value=value.split('。',1)[0]
    elif not finished and len(value)>=30 and '，' in value:value=value.rsplit('，',1)[0]
    value=re.sub(r'^(?:照片|图像)中','画面中',value)
    value=re.sub(r'(?:一位|一名|一个)?(?:年轻的?|中年的?)?(?:女性|男性|男子|女子|女孩|男孩|女士|男士)','人物',value)
    if len(re.findall(r'[\u4e00-\u9fff]',value))<4:raise ValueError('No usable image observation')
    return value.rstrip('，、；：。！？')+'。'


class GeneralVLMReporter:
    """Generate image facts and activity context with local generative models."""
    def generate(self,photo):
        from concurrent.futures import ThreadPoolExecutor
        from report_general_vlm import generate
        warm_local_model()
        def background():
            start=time.monotonic();writer=ReportWriter()
            payload={'messages':[{'role':'system','content':'为校园科技节纪念报纸写一句15至25字的中文背景报道。只依据提供的作品功能，不描述当前照片中的人或场景，不用比喻，不说已经打印。只输出一个完整句子。'},
                {'role':'user','content':'AI动漫拍报机把摄像头影像转成动漫，生成科技节纪念报纸。请写出它的纪念意义。/no_think'}],
                'max_tokens':64,'temperature':.2,'top_p':.9,'cache_prompt':True,'stream':False,
                'chat_template_kwargs':{'enable_thinking':False},
                'grammar':'root ::= "AI" [一-鿿，、]{10,36} "。"'}
            text=writer.complete(WRITER_ENDPOINT,payload,start+12)
            return text,round(time.monotonic()-start,3)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(background)
            result=generate(photo)
            context,self.writer_seconds=future.result()
        self.acceleration_fallback=result.get('acceleration_fallback')
        self.vision_profile={k:result.get(k) for k in ['startup_seconds','inference_seconds','encoder_load_seconds','encoder_seconds','encoder_cleanup_seconds','http_seconds']}
        self.backend=result['backend'];self.vision_model=result['model']
        self.vision_decoder='generative multimodal decoder'
        self.vision_seconds=result['seconds'];self.last_caption=result['text']
        self.writing_mode='parallel generative image facts and activity context'
        return clean_report(report_fact_sentence(self.last_caption)+context)


def make_report(photo,enabled,reporter=None):
    if not enabled:return {'enabled':False,'state':'disabled'}
    start=time.monotonic()
    try:
        engine=reporter or GeneralVLMReporter();text=engine.generate(photo)
        result={'enabled':True,'state':'generated','text':text,
                'seconds':round(time.monotonic()-start,2)}
        if isinstance(getattr(engine,'last_caption',None),str):result['observation']=engine.last_caption
        if isinstance(getattr(engine,'backend',None),str):result['backend']=engine.backend
        if isinstance(getattr(engine,'vision_model',None),str):result['vision_model']=engine.vision_model
        if isinstance(getattr(engine,'vision_decoder',None),str):result['vision_decoder']=engine.vision_decoder
        if isinstance(getattr(engine,'subject',None),dict):result['subject']=engine.subject
        if isinstance(getattr(engine,'vision_seconds',None),(int,float)):result['vision_seconds']=engine.vision_seconds
        if isinstance(getattr(engine,'vision_profile',None),dict):result['vision_profile']=engine.vision_profile
        if isinstance(getattr(engine,'writer_seconds',None),(int,float)):result['writer_seconds']=engine.writer_seconds
        if isinstance(getattr(engine,'writing_mode',None),str):result['writing_mode']=engine.writing_mode
        if isinstance(getattr(engine,'acceleration_fallback',None),str):result['acceleration_fallback']=engine.acceleration_fallback
        return result
    except Exception as error:
        return {'enabled':True,'state':'fallback','reason':type(error).__name__,
                'seconds':round(time.monotonic()-start,2)}
