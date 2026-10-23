"""Local-only gesture capture and A5 newspaper; no camera data is uploaded."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, math, os, queue, subprocess, threading, time, uuid
import numpy as np
from festival_settings import DEFAULT_OPTIONS, normalize_options
from festival_weather import WeatherCache,weather_label

ROOT = Path(__file__).resolve().parent

def victory(points):
    """Rotation-independent finger extension, rejecting fists and open palms."""
    p = np.asarray(points, dtype=float).reshape(21, 3)
    def extended(base):
        a, b = p[base] - p[base+1], p[base+3] - p[base+1]
        cosine = np.dot(a, b) / max(np.linalg.norm(a)*np.linalg.norm(b), 1e-9)
        return cosine < -0.55 and np.linalg.norm(p[base+3]-p[0]) > 1.15*np.linalg.norm(p[base+1]-p[0])
    return extended(5) and extended(9) and not extended(13) and not extended(17)

class GestureLatch:
    def __init__(self):
        self.armed=True; self.since=None; self.absent=None
    def update(self, detected, now):
        if detected:
            self.absent=None
            if self.since is None:self.since=now
            if self.armed and now-self.since >= .45:
                self.armed=False;return True
        else:
            self.since=None
            if self.absent is None:self.absent=now
            if now-self.absent >= 1:self.armed=True
        return False

def newspaper(photo, target, captured=None, weather=None):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from PIL import Image
    fonts=[os.environ.get('FESTIVAL_FONT',''),'/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc','C:/Windows/Fonts/msyh.ttc']
    font=next((p for p in fonts if p and Path(p).is_file()),None)
    if not font:raise RuntimeError('请安装中文字体 fonts-wqy-zenhei')
    if 'FestivalChinese' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('FestivalChinese',font))
    width,height=148*mm,210*mm
    c=canvas.Canvas(str(target),pagesize=(width,height));c.setTitle('北京市第65中学2026年校园科技节')
    c.setFillColorRGB(1,1,1);c.rect(0,0,width,height,fill=1,stroke=0)
    c.setFillColorRGB(0,0,0);c.setStrokeColorRGB(0,0,0)
    def text(x,y,s,size,font='FestivalChinese',align='left'):
        c.setFont(font,size)
        method={'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align]
        method(x*mm,y*mm,s)
    def rule(y,weight=.5):c.setLineWidth(weight);c.line(8*mm,y*mm,140*mm,y*mm)
    c.drawImage(str(ROOT/'assets/school-emblem.png'),8*mm,185*mm,17*mm,17*mm,preserveAspectRatio=True,anchor='c',mask='auto')
    text(30,191,'第65中学 · 科技现场',21)
    text(30,182,'北京市第65中学2026年校园科技节',8.5)
    text(140,196,'2026',14,font='Helvetica-Bold',align='right')
    text(140,187,'校园纪念刊',7.5,align='right')
    rule(177,1)
    when=captured or datetime.now(ZoneInfo('Asia/Shanghai'))
    text(8,172,when.strftime('%Y.%m.%d  %H:%M:%S'),7.4)
    text(140,172,weather_label(weather,when),7.4,align='right')
    text(74,158,'做中学科学 实践促创新',20,align='center')
    text(74,150,'用一次亲身体验，留下今天的科技记忆',8.5,align='center')
    image=Image.open(photo).convert('RGB');photo_height=min(90.,132*image.height/max(1,image.width));bottom=144-photo_height
    box=(8*mm,bottom*mm,132*mm,photo_height*mm)
    c.drawImage(ImageReader(image),*box,preserveAspectRatio=True,anchor='c')
    text(8,bottom-4.5,'现场影像 / 人工智能动漫照相馆',6.5)
    text(140,bottom-4.5,'校园科技节 · 专属留念',6.5,align='right')
    rule(bottom-8,.4)
    footer=bottom-16
    text(8,footer,'镜头里的科技体验',11)
    text(79,footer,'把问题交给实践',11)
    left=['摄像头记录眼前的真实场景，','人工智能将它转化为动漫影像。','这一张照片，留住今天的相遇，','也记录我们与科技的一次对话。']
    right=['从一次观察，到一次动手；','从一个想法，到一次验证。','在探索中学习，让好奇心','成为下一次发现的起点。']
    for index,(a,b) in enumerate(zip(left,right)):
        text(8,footer-7-index*4.5,a,7.7);text(79,footer-7-index*4.5,b,7.7)
    rule(16,.6)
    text(8,10,'第65中学 · 在体验中学习，在实践中创新',6.2)
    source='天气：Open-Meteo' if weather_label(weather,when)!='北京 天气暂不可用' else '天气未联网更新'
    text(140,10,source,5.5,align='right')
    c.showPage();c.save()

def submit_print(pdf, runner=subprocess.run, printer='S100_Festival'):
    """Exactly one submission attempt; ambiguous failures are never auto-retried."""
    printer=normalize_options({'printer':printer})['printer']
    p=runner(['lp','-d',printer,'-n','1','-o','media=iso_a5_148x210mm','-o','orientation-requested=3','-o','sides=one-sided','-o','media-type=stationery','-o','media-source=auto','-o','print-color-mode=color',str(pdf)],capture_output=True,text=True,timeout=30)
    if p.returncode:raise RuntimeError(p.stderr.strip() or '打印提交失败')
    return p.stdout.strip()

def dispatch_output(pdf, options, submitter=submit_print):
    options=normalize_options(options)
    if not options['print_enabled']:return {'state':'pdf_only','printer':options['printer']}
    return {'state':'submitted','printer':options['printer'],'job':submitter(pdf,printer=options['printer'])}

class Festival:
    def __init__(self, latest, notify, running, configuration=lambda:dict(DEFAULT_OPTIONS)):
        self.latest=latest;self.notify=notify;self.running=running
        self.configuration=configuration
        self.weather=WeatherCache(ROOT/'weather-cache.json',running)
        self.lock=threading.Lock();self.deadline=None;self.min_sequence=None
        self.status='比 ✌ 保持片刻，3 秒后拍照';self.jobs=queue.Queue(maxsize=2)
        self.directory=ROOT/'captures';self.directory.mkdir(exist_ok=True)
        self.history=sorted(self.directory.glob('*/photo.jpg'))[-100:]
        self.worker=threading.Thread(target=self.save_loop,daemon=True);self.worker.start()
        self.detector=threading.Thread(target=self.gesture_loop,daemon=True);self.detector.start()
    def trigger(self):
        with self.lock:
            if self.deadline is not None or self.min_sequence is not None or self.jobs.full():return False
            self.deadline=time.monotonic()+3;return True
    def tick(self):
        with self.lock:
            if self.deadline is not None:
                remaining=self.deadline-time.monotonic()
                if remaining>0:return str(math.ceil(remaining))
                self.min_sequence=self.latest()[0];self.deadline=None
            return '正在拍照…' if self.min_sequence is not None else ''
    def accept(self, rgb, sequence):
        with self.lock:
            if self.min_sequence is None or sequence<self.min_sequence:return
            self.min_sequence=None
            try:self.jobs.put_nowait((rgb.copy(),dict(getattr(self,'configuration',lambda:DEFAULT_OPTIONS)())));self.status='正在生成报纸…'
            except queue.Full:self.status='打印任务繁忙，请稍后再拍'
    def gesture_loop(self):
        try:
            import cv2
            from festival_vendor.mp_palmdet import MPPalmDet
            from festival_vendor.mp_handpose import MPHandPose
            palm=MPPalmDet(str(ROOT/'models/palm_detection_mediapipe_2023feb.onnx'),scoreThreshold=.65,topK=32)
            hand=MPHandPose(str(ROOT/'models/handpose_estimation_mediapipe_2023feb.onnx'),confThreshold=.8)
            latch=GestureLatch();last=-1
            while self.running():
                start=time.monotonic();seq,frame=self.latest()
                if frame is not None and seq!=last:
                    last=seq;h,w=frame.shape[:2];small=cv2.resize(frame,(int(w*min(1,640/max(w,h))),int(h*min(1,640/max(w,h)))))
                    detected=False
                    try:
                        for row in sorted(palm.infer(small),key=lambda r:-r[-1])[:2]:
                            pose=hand.infer(small,row)
                            if pose is not None and victory(pose[67:130]):detected=True;break
                    except cv2.error as error:print('GESTURE_FRAME',str(error)[:180],flush=True)
                    if latch.update(detected,time.monotonic()):self.trigger()
                time.sleep(max(.02,.30-(time.monotonic()-start)))
        except Exception as error:
            self.status='手势识别不可用，可按空格拍照';print('GESTURE_ERROR',str(error),flush=True)
    def save_loop(self):
        from PIL import Image
        while self.running() or not self.jobs.empty():
            try:rgb,options=self.jobs.get(timeout=.5)
            except queue.Empty:
                if hasattr(self,'last_job') and self.configuration()['print_enabled']:
                    try:
                        p=subprocess.run(['lpstat','-p',self.last_printer],capture_output=True,text=True,timeout=3)
                        if 'Waiting for printer' in p.stdout or 'disabled' in p.stdout:self.status='打印机离线，请开机；已有任务正在等待'
                        elif 'idle' in p.stdout:self.status='打印队列就绪 · 比 ✌ 再拍一张'
                    except (OSError,subprocess.TimeoutExpired):pass
                continue
            folder=self.directory/(datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
            record={'state':'saving','options':options}
            def journal():
                temp=folder/'record.tmp';temp.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8');temp.replace(folder/'record.json')
            try:
                photo=folder/'photo.jpg';Image.fromarray(rgb).save(photo,quality=96,subsampling=0)
                self.history=(self.history+[photo])[-100:];self.notify(photo)
                pdf=folder/'newspaper.pdf';weather=self.weather.snapshot() if hasattr(self,'weather') else None;newspaper(photo,pdf,weather=weather)
                record['weather']=weather
                record['state']='submitting' if options['print_enabled'] else 'generating_pdf';journal()
                record.update(dispatch_output(pdf,options));journal()
                if record['state']=='submitted':
                    self.last_job=record['job'];self.last_printer=record['printer'];self.status='照片已保存，报纸已提交打印'
                else:self.status='照片和报纸 PDF 已保存，未打印'
            except Exception as error:
                record.update(state='needs_attention',error=str(error));journal()
                self.status='照片已保存；打印异常，请检查打印机';print('FESTIVAL_ERROR',str(error),flush=True)
            finally:self.jobs.task_done()
