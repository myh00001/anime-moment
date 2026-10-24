"""Gesture capture and A5 newspaper, with opt-in local or cloud reporting."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, math, os, queue, subprocess, threading, time, uuid
import numpy as np
from festival_settings import DEFAULT_OPTIONS, normalize_options
from festival_weather import WeatherCache,weather_label
from weather_icon import draw_weather_icon
from local_report import make_report
from report_router import generate_report

ROOT = Path(__file__).resolve().parent

def gesture_regions(width, height):
    """Overlapping native-resolution search windows for distant hands."""
    side=max(1,int(min(width,height)*.28))
    stride=max(1,int(side*.65))
    xs=np.linspace(0,max(0,width-side),int(math.ceil(max(0,width-side)/stride))+1).astype(int)
    ys=np.linspace(0,max(0,height-side),int(math.ceil(max(0,height-side)/stride))+1).astype(int)
    regions=[(int(x),int(y),int(x)+side,int(y)+side) for y in ys for x in xs]
    # Spread consecutive searches across the entire image, including corners.
    # Every window appears exactly once per sweep; there is no central priority.
    ordered=[]
    for x,y in [(0,0),(width-side,height-side),(width-side,0),(0,height-side)]:
        corner=(x,y,x+side,y+side)
        if corner in regions:ordered.append(corner);regions.remove(corner)
    while regions:
        index=max(range(len(regions)),key=lambda i:min(
            (regions[i][0]-r[0])**2+(regions[i][1]-r[1])**2 for r in ordered))
        ordered.append(regions.pop(index))
    return ordered

def victory(points):
    """Rotation-independent finger extension, rejecting fists and open palms."""
    p = np.asarray(points, dtype=float).reshape(21, 3)
    def extended(base,angle=-.55,reach=1.15):
        a, b = p[base] - p[base+1], p[base+3] - p[base+1]
        cosine = np.dot(a, b) / max(np.linalg.norm(a)*np.linalg.norm(b), 1e-9)
        return cosine < angle and np.linalg.norm(p[base+3]-p[0]) > reach*np.linalg.norm(p[base+1]-p[0])
    # Allow visibly bent index/middle fingers; keep the other fingers folded
    # requirement unchanged to distinguish a V sign from an open palm.
    return extended(5,-.10,1.02) and extended(9,-.10,1.02) and not extended(13) and not extended(17)

def pose_victory(pose):
    """Accept image-plane geometry when uncertain depth hides a visible V sign."""
    if pose is None:return False
    if victory(pose[67:130]):return True
    points=np.asarray(pose[4:67],dtype=float).reshape(21,3).copy()
    points[:,2]=0
    return victory(points)

class GestureLatch:
    def __init__(self):
        self.armed=True; self.absent=None
    def update(self, detected, now):
        if detected:
            self.absent=None
            if self.armed:
                self.armed=False;return True
        else:
            if self.absent is None:self.absent=now
            if now-self.absent >= 1:self.armed=True
        return False

def newspaper(photo, target, captured=None, weather=None,report=None):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from PIL import Image
    fonts=[os.environ.get('FESTIVAL_FONT',''),str(ROOT/'assets/fonts/msyh.ttc'),'C:/Windows/Fonts/msyh.ttc']
    font=next((p for p in fonts if p and Path(p).is_file()),None)
    bold_fonts=[os.environ.get('FESTIVAL_BOLD_FONT',''),str(ROOT/'assets/fonts/msyhbd.ttc'),'C:/Windows/Fonts/msyhbd.ttc']
    bold_font=next((p for p in bold_fonts if p and Path(p).is_file()),None)
    if not font or not bold_font:raise RuntimeError('请配置微软雅黑常规及粗体字体 msyh.ttc / msyhbd.ttc')
    if 'FestivalChinese' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('FestivalChinese',font))
    if 'FestivalChineseBold' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('FestivalChineseBold',bold_font))
    width,height=148*mm,210*mm
    c=canvas.Canvas(str(target),pagesize=(width,height),initialFontName='FestivalChinese');c.setTitle('北京市第六十五中学2026年校园科技节')
    c.setFillColorRGB(1,1,1);c.rect(0,0,width,height,fill=1,stroke=0)
    c.setFillColorRGB(0,0,0);c.setStrokeColorRGB(0,0,0)
    def text(x,y,s,size,font='FestivalChinese',align='left',bold=False):
        font='FestivalChineseBold' if bold or font in ('Helvetica-Bold','FestivalChineseBold') else 'FestivalChinese'
        c.setFont(font,size)
        method={'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align]
        method(x*mm,y*mm,s)
    def rule(y,weight=.5):c.setLineWidth(weight);c.line(8*mm,y*mm,140*mm,y*mm)
    def reverse_label(x,y,w,label,size=12):
        c.setFillColorRGB(.55,.55,.55);c.rect(x*mm,(y-2.4)*mm,w*mm,8.5*mm,fill=1,stroke=0)
        c.setFillColorRGB(1,1,1);text(x+3,y,label,size,bold=True);c.setFillColorRGB(0,0,0)
    def wrap(value,size,limit):
        rows=[];line=''
        for char in value:
            if line and pdfmetrics.stringWidth(line+char,'FestivalChinese',size)>limit*mm:
                if char in '，。、；：！？）》”' and len(line)>1:rows.append(line[:-1]);line=line[-1]+char
                else:rows.append(line);line=char
            else:line+=char
        if line:rows.append(line)
        return rows
    c.drawImage(str(ROOT/'assets/school-emblem.png'),7*mm,179*mm,25*mm,25*mm,preserveAspectRatio=True,anchor='c',mask='auto')
    text(35,194,'漫像时刻',24,bold=True)
    text(35,187,'AI 动漫拍报机',10.5)
    text(35,181,'北京市第六十五中学2026年校园科技节',10)
    text(140,196,'2026',14,font='Helvetica-Bold',align='right')
    text(140,188,'校园纪念刊',9.5,align='right')
    rule(177,1)
    when=captured or datetime.now(ZoneInfo('Asia/Shanghai'))
    text(8,172,when.strftime('%Y.%m.%d  %H:%M:%S'),10)
    available=weather_label(weather,when)!='北京 天气暂不可用'
    temperature=f"{float(weather['temperature']):.0f}°C" if available else '暂无'
    temp_width=pdfmetrics.stringWidth(temperature,'FestivalChinese',10)/mm
    city_width=pdfmetrics.stringWidth('北京','FestivalChinese',10)/mm
    icon_size=3.6;gap=1.4
    group_left=140-temp_width-icon_size-city_width-2*gap
    text(group_left,172,'北京',10)
    draw_weather_icon(c,(group_left+city_width+gap)*mm,171.7*mm,icon_size*mm,int(weather['code']) if available else None)
    text(140,172,temperature,10,align='right')
    c.setFillColorRGB(.55,.55,.55);c.rect(8*mm,153.5*mm,132*mm,13*mm,fill=1,stroke=0);c.setFillColorRGB(1,1,1)
    text(74,158,'做中学科学 实践促创新',22,align='center',bold=True);c.setFillColorRGB(0,0,0)
    text(74,147,'用一次亲身体验，留下今天的科技记忆',10.5,align='center')
    left=['基于 RDK S100，将摄像头画面','实时转化为动漫风格。比出 V 手势，','即可倒计时拍照，并自动生成、','打印专属科技节纪念报纸。']
    right=['看见 AI 的实时创作，','用一个手势留下此刻，','让科技节的体验与回忆，','成为一份可以带走的纪念。']
    if report:right=[report]
    columns=[(x,[row for part in paragraph for row in wrap(part,10.5,limit)]) for x,paragraph,limit in [(8,left,62),(79,right,61)]]
    footer_min=27+(max(len(rows) for _,rows in columns)-1)*5.3
    with Image.open(photo) as source:
        photo_height=min(140-footer_min-13,132*source.height/max(1,source.width))
        image=str(photo) if source.format=='JPEG' and source.mode=='RGB' else ImageReader(source.convert('RGB'))
    bottom=140-photo_height
    box=(8*mm,bottom*mm,132*mm,photo_height*mm)
    c.drawImage(image,*box,preserveAspectRatio=True,anchor='c')
    text(8,bottom-4.5,'镜头里的科技节',9)
    text(140,bottom-4.5,'AI 动漫留念',8.5,align='right')
    footer=bottom-13
    reverse_label(8,footer,62,'作品说明')
    reverse_label(79,footer,61,'现场报道 · AI生成' if report else '可看 · 可玩 · 可带走')
    for x,rows in columns:
        for index,line in enumerate(rows):
            text(x,footer-8-index*5.3,line,10.5)
    rule(16,.6)
    text(74,11,'北京市第六十五中学2026年校园科技节',8.5,align='center')
    text(74,6,'在体验中学习，在实践中创新',7.5,align='center')
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
    def __init__(self, latest, notify, running, configuration=lambda:dict(DEFAULT_OPTIONS), wait_inference_idle=lambda:True):
        self.latest=latest;self.notify=notify;self.running=running
        self.configuration=configuration;self.wait_inference_idle=wait_inference_idle
        self.weather=WeatherCache(ROOT/'weather-cache.json',running)
        self.gesture_released=threading.Event();self.gesture_released.set()
        self.lock=threading.Lock();self.deadline=None;self.min_sequence=None;self.shutter_at=0;self.pickup_at=0;self.ai_busy_at=0;self.report_stage=''
        self.status='比 ✌ 即可开始 3 秒拍照倒计时';self.jobs=queue.Queue(maxsize=2)
        self.directory=ROOT/'captures';self.directory.mkdir(exist_ok=True)
        self.history=sorted(self.directory.glob('*/photo.jpg'))[-100:]
        self.worker=threading.Thread(target=self.save_loop,daemon=True);self.worker.start()
        self.detector=threading.Thread(target=self.gesture_loop,daemon=True);self.detector.start()
    def trigger(self):
        with self.lock:
            if getattr(self,'ai_busy_at',0) or self.deadline is not None or self.min_sequence is not None or self.jobs.full():return False
            self.deadline=time.monotonic()+3;return True
    def tick(self):
        with self.lock:
            if self.deadline is not None:
                remaining=self.deadline-time.monotonic()
                if remaining>0:return str(math.ceil(remaining))
                self.min_sequence=self.latest()[0];self.deadline=None
            return '正在拍照…' if self.min_sequence is not None else ''
    def accept(self, rgb, sequence, original_bgr=None):
        with self.lock:
            if self.min_sequence is None or sequence<self.min_sequence:return
            self.min_sequence=None
            options=dict(getattr(self,'configuration',lambda:DEFAULT_OPTIONS)())
            original=original_bgr.copy() if original_bgr is not None else None
            try:
                if options.get('ai_report',False):
                    self.ai_busy_at=time.monotonic();self.report_stage='云端 AI 正在生成报道' if options.get('report_provider')=='deepseek' else 'AI 正在生成报道';self.pickup_at=0
                self.jobs.put_nowait((rgb.copy(),options,original));self.shutter_at=time.monotonic();self.status='正在生成报纸…'
            except queue.Full:
                self.ai_busy_at=0;self.report_stage='';self.status='打印任务繁忙，请稍后再拍'
    def yolo_gesture_loop(self,detector):
        self.gesture_backend='YOLOv10n · S100 BPU'
        print('GESTURE_RUNTIME',self.gesture_backend,flush=True)
        latch=GestureLatch();last=-1;last_status=0
        while self.running():
            if getattr(self,'ai_busy_at',0):
                if detector.runtime is not None:
                    detector.runtime=None
                    import gc;gc.collect()
                self.gesture_released.set()
                time.sleep(.05);continue
            if detector.runtime is None:
                from hbm_runtime import HB_HBMRuntime
                self.gesture_released.clear()
                detector.runtime=HB_HBMRuntime(str(ROOT/'models/hagrid_gesture.hbm'))
                detector.name=detector.runtime.model_names[0]
            start=time.monotonic();seq,frame=self.latest();detected=False
            if frame is not None and seq!=last:
                last=seq;detected=detector.detect(frame)
                if latch.update(detected,time.monotonic()):self.trigger()
                if time.monotonic()-last_status>2:
                    last_status=time.monotonic()
                    (ROOT/'gesture-status.json').write_text(json.dumps({'backend':self.gesture_backend,'input_size':detector.size,'threshold':detector.threshold,'confirmation_seconds':.1,'processing_ms':(last_status-start)*1000,'time':time.time()}))
            interval=.05 if detected and latch.armed else (.2 if not latch.armed else .12)
            time.sleep(max(.02,interval-(time.monotonic()-start)))

    def gesture_loop(self):
        try:
            model=ROOT/'models/hagrid_gesture.hbm'
            metadata=ROOT/'gesture-model.json'
            if model.is_file() and metadata.is_file() and not (ROOT/'gesture-yolo-disabled').exists():
                from gesture_yolo import BpuGestureDetector
                options=json.loads(metadata.read_text())
                self.gesture_released.clear()
                detector=BpuGestureDetector(model,size=options['input_size'],threshold=options.get('threshold',.5))
                self.yolo_gesture_loop(detector);return
        except Exception as error:
            print('GESTURE_YOLO_FALLBACK',type(error).__name__,str(error)[:160],flush=True)
        self.gesture_released.set()
        self.gesture_backend='MediaPipe · CPU'
        try:
            import cv2
            from festival_vendor.mp_palmdet import MPPalmDet
            from festival_vendor.mp_handpose import MPHandPose
            palm=MPPalmDet(str(ROOT/'models/palm_detection_mediapipe_2023feb.onnx'),scoreThreshold=.25,topK=32)
            hand=MPHandPose(str(ROOT/'models/handpose_estimation_mediapipe_2023feb.onnx'),confThreshold=.35)
            from gesture_runtime import configure
            print('GESTURE_RUNTIME',configure(palm,hand,ROOT),flush=True)
            latch=GestureLatch();last=-1;region_index=0;locked_region=None;region_shape=None;locked_until=0
            while self.running():
                if getattr(self,'ai_busy_at',0):
                    time.sleep(.1);continue
                start=time.monotonic();seq,frame=self.latest()
                if frame is not None and seq!=last:
                    last=seq;h,w=frame.shape[:2]
                    detected=False
                    try:
                        if region_shape!=(w,h):
                            regions=gesture_regions(w,h);region_shape=(w,h);region_index=0;locked_region=None
                        candidates=[]
                        if locked_region in regions:candidates.append(locked_region)
                        candidates.append(None)  # Full frame preserves close-range detection.
                        candidates.extend(regions[(region_index+i)%len(regions)] for i in range(6))
                        scanned=0
                        seen=set()
                        for region in candidates:
                            if region in seen:continue
                            seen.add(region)
                            if region is None:view=frame
                            else:
                                x1,y1,x2,y2=region;view=frame[y1:y2,x1:x2]
                            if region is not None and region!=locked_region:
                                scanned+=1;region_index=(region_index+1)%len(regions)
                            vh,vw=view.shape[:2];scale=min(1,640/max(vw,vh))
                            small=cv2.resize(view,(max(1,int(vw*scale)),max(1,int(vh*scale))))
                            for row in sorted(palm.infer(small),key=lambda r:-r[-1])[:4]:
                                # Palm search is small, but recover finger landmarks from
                                # native pixels instead of the downsampled search image.
                                native_row=row.copy();native_row[:18]/=scale
                                pose=hand.infer(view,native_row)
                                if pose_victory(pose):detected=True;break
                            if detected:
                                locked_region=region;locked_until=time.monotonic()+.8;break
                            # Scan more small windows when affordable without allowing
                            # gesture search to monopolize CPU needed by the live image.
                            if scanned>=3 and time.monotonic()-start>=.15:break
                        if not detected and time.monotonic()>locked_until:locked_region=None
                    except cv2.error as error:print('GESTURE_FRAME',str(error)[:180],flush=True)
                    if latch.update(detected,time.monotonic()):self.trigger()
                time.sleep(max(.02,.18-(time.monotonic()-start)))
        except Exception as error:
            self.status='手势识别不可用，可按空格拍照';print('GESTURE_ERROR',str(error),flush=True)
    def save_loop(self):
        from PIL import Image
        while self.running() or not self.jobs.empty():
            try:rgb,options,original_bgr=self.jobs.get(timeout=.5)
            except queue.Empty:
                if hasattr(self,'last_job') and self.configuration()['print_enabled']:
                    try:
                        p=subprocess.run(['lpstat','-p',self.last_printer],capture_output=True,text=True,timeout=3)
                        if 'Waiting for printer' in p.stdout or 'disabled' in p.stdout:self.status='打印机离线，请开机；已有任务正在等待'
                        elif 'idle' in p.stdout:self.status='打印队列就绪 · 比 ✌ 再拍一张'
                    except (OSError,subprocess.TimeoutExpired):pass
                continue
            folder=self.directory/(datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
            record={'state':'saving','options':options}
            def journal():
                temp=folder/'record.tmp';temp.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8');temp.replace(folder/'record.json')
            try:
                folder.mkdir()
                photo=folder/'photo.jpg';Image.fromarray(rgb).save(photo,quality=96,subsampling=0)
                self.history=(self.history+[photo])[-100:];self.notify(photo)
                inference_ready=True
                if options.get('ai_report',False):
                    self.status='照片已保存，正在本地生成报道…'
                    inference_ready=getattr(self,'wait_inference_idle',lambda:True)()
                    if inference_ready and hasattr(self,'gesture_released'):
                        inference_ready=self.gesture_released.wait(5)
                original=folder/'original.jpg'
                if original_bgr is not None:
                    Image.fromarray(original_bgr[:,:,::-1]).save(original,quality=96,subsampling=0)
                    record['report_source']='original.jpg'
                report=generate_report(original,options,ROOT,local=make_report) if inference_ready else {'enabled':True,'state':'fallback','reason':'InferenceNotIdle'}
                record['ai_report']=report;journal()
                if options.get('ai_report',False):self.report_stage='正在排版纪念报纸'
                pdf=folder/'newspaper.pdf';weather=self.weather.snapshot() if hasattr(self,'weather') else None;newspaper(photo,pdf,weather=weather,report=report.get('text'))
                record['weather']=weather
                record['state']='submitting' if options['print_enabled'] else 'generating_pdf';journal()
                if options.get('ai_report',False):self.report_stage='正在提交打印' if options['print_enabled'] else '正在保存报纸 PDF'
                record.update(dispatch_output(pdf,options));journal()
                if record['state']=='submitted':
                    self.pickup_at=time.monotonic()
                    self.last_job=record['job'];self.last_printer=record['printer'];self.status='照片已保存，报纸已提交打印'
                else:self.status='照片和报纸 PDF 已保存，未打印'
            except Exception as error:
                record.update(state='needs_attention',error=str(error));journal()
                self.status='照片已保存；打印异常，请检查打印机';print('FESTIVAL_ERROR',str(error),flush=True)
            finally:
                if options.get('ai_report',False):
                    with self.lock:self.ai_busy_at=0;self.report_stage=''
                self.jobs.task_done()
