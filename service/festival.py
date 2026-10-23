"""Local-only gesture capture and A5 newspaper; no camera data is uploaded."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, math, os, queue, subprocess, threading, time, uuid
import numpy as np

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

def newspaper(photo, target, captured=None):
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
    c=canvas.Canvas(str(target),pagesize=(width,height));c.setTitle('北京市第六十五中学2026年校园科技节')
    c.setFillColorRGB(.985,.977,.951);c.rect(0,0,width,height,fill=1,stroke=0)
    c.setFillColorRGB(.10,.13,.16);c.setStrokeColorRGB(.10,.13,.16)
    def text(x,y,s,size):c.setFont('FestivalChinese',size);c.drawString(x*mm,y*mm,s)
    c.drawImage(str(ROOT/'assets/school-emblem.png'),8*mm,178*mm,23*mm,23*mm,preserveAspectRatio=True,anchor='c',mask='auto')
    text(35,193,'六五校园科技报',23)
    text(35,182,'2026 校园科技节 · 留念特刊',9)
    c.setLineWidth(1.2);c.line(8*mm,174*mm,140*mm,174*mm)
    text(8,163,'做中学科学 实践促创新',17)
    text(8,154,'北京市第六十五中学2026年校园科技节',9.5)
    when=captured or datetime.now(ZoneInfo('Asia/Shanghai'))
    text(8,145,'AI 动漫照相馆',8)
    text(99,145,when.strftime('%Y年%m月%d日'),8)
    image=Image.open(photo).convert('RGB');box=(8*mm,64*mm,132*mm,74.25*mm)
    c.setFillColorRGB(1,1,1);c.rect(*box,fill=1,stroke=0)
    c.drawImage(ImageReader(image),*box,preserveAspectRatio=True,anchor='c')
    c.setFillColorRGB(.10,.13,.16);text(8,53,'今日科技主角',14)
    text(8,43,'比一个 V，记录此刻的你。',10)
    text(8,30,'当科学遇见创意，让想象成为画面。',9)
    c.setLineWidth(.5);c.line(8*mm,18*mm,140*mm,18*mm)
    text(8,11,'六五校园 · 科技与创意同行',8);text(106,11,when.strftime('%H:%M:%S')+'  留念',8)
    c.showPage();c.save()

def submit_print(pdf, runner=subprocess.run):
    """Exactly one submission attempt; ambiguous failures are never auto-retried."""
    p=runner(['lp','-d','S100_Festival','-n','1','-o','media=iso_a5_148x210mm','-o','orientation-requested=3','-o','sides=one-sided','-o','HPPJLColorAsGray=off','-o','print-color-mode=color',str(pdf)],capture_output=True,text=True,timeout=30)
    if p.returncode:raise RuntimeError(p.stderr.strip() or '打印提交失败')
    return p.stdout.strip()

class Festival:
    def __init__(self, latest, notify, running):
        self.latest=latest;self.notify=notify;self.running=running
        self.lock=threading.Lock();self.deadline=None;self.min_sequence=None
        self.status='比 ✌ 保持片刻，3 秒后拍照';self.jobs=queue.Queue(maxsize=2)
        self.directory=ROOT/'captures';self.directory.mkdir(exist_ok=True)
        self.history=sorted(self.directory.glob('*/photo.jpg'))[-12:]
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
            try:self.jobs.put_nowait(rgb.copy());self.status='正在生成报纸…'
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
            self.status='手势识别不可用，可点击拍照';print('GESTURE_ERROR',str(error),flush=True)
    def save_loop(self):
        from PIL import Image
        while self.running() or not self.jobs.empty():
            try:rgb=self.jobs.get(timeout=.5)
            except queue.Empty:
                if hasattr(self,'last_job'):
                    try:
                        p=subprocess.run(['lpstat','-p','S100_Festival'],capture_output=True,text=True,timeout=3)
                        if 'Waiting for printer' in p.stdout or 'disabled' in p.stdout:self.status='打印机离线，请开机；已有任务正在等待'
                        elif 'idle' in p.stdout:self.status='打印队列就绪 · 比 ✌ 再拍一张'
                    except (OSError,subprocess.TimeoutExpired):pass
                continue
            folder=self.directory/(datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
            record={'state':'saving'}
            def journal():
                temp=folder/'record.tmp';temp.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8');temp.replace(folder/'record.json')
            try:
                photo=folder/'photo.jpg';Image.fromarray(rgb).save(photo,quality=96,subsampling=0)
                self.history=(self.history+[photo])[-12:];self.notify(photo)
                pdf=folder/'newspaper.pdf';newspaper(photo,pdf)
                record['state']='submitting';journal()
                record['job']=submit_print(pdf);self.last_job=record['job'];record['state']='submitted';journal()
                self.status='照片已保存，报纸已提交打印'
            except Exception as error:
                record.update(state='needs_attention',error=str(error));journal()
                self.status='照片已保存；打印异常，请检查打印机';print('FESTIVAL_ERROR',str(error),flush=True)
            finally:self.jobs.task_done()
