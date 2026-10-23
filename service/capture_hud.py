"""Lightweight vector capture overlay; independent of inference and printing."""
import math
import gi
gi.require_version('Pango','1.0')
gi.require_version('PangoCairo','1.0')
from gi.repository import Pango,PangoCairo

def draw_capture_hud(c,width,height,remaining=None,shot_age=None,waiting=False,pickup_age=None):
    scale=min(width/1280,height/720)*1.3
    if scale<=0:return
    c.save();c.translate(width/2,height/2);c.scale(scale,scale)
    def text(value,y,size,bold=False,alpha=1):
        layout=PangoCairo.create_layout(c)
        font=Pango.FontDescription('Microsoft YaHei')
        font.set_absolute_size(size*Pango.SCALE)
        if bold:font.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(font);layout.set_text(value,-1)
        w,h=layout.get_pixel_size();c.set_source_rgba(1,1,1,alpha)
        c.move_to(-w/2,y-h/2);PangoCairo.show_layout(c,layout)
    if remaining is not None and remaining>0:
        progress=max(0,min(1,(3-remaining)/3))
        pulse=1+.035*math.exp(-7*((3-remaining)%1))
        c.set_source_rgba(.025,.04,.055,.64);c.arc(0,-15,99,0,2*math.pi);c.fill()
        c.set_line_width(3);c.set_source_rgba(1,1,1,.19);c.arc(0,-15,99,0,2*math.pi);c.stroke()
        c.set_source_rgba(.64,.93,.85,1);c.arc(0,-15,99,-math.pi/2,-math.pi/2+max(.003,progress*2*math.pi));c.stroke()
        c.save();c.translate(0,-20);c.scale(pulse,pulse)
        text(str(math.ceil(remaining)),0,112,True);c.restore()
        text('准备好，留下这一刻',121,24,True)
        text('看向镜头 · 可以放下手势',159,16,alpha=.85)
        c.set_source_rgba(1,1,1,.75);c.set_line_width(2)
        for sx in [-1,1]:
            for sy in [-1,1]:
                x=sx*220;y=sy*175-12
                c.move_to(x-sx*25,y);c.line_to(x,y);c.line_to(x,y-sy*25)
        c.stroke()
    elif waiting:
        c.set_source_rgba(.025,.04,.055,.7);c.arc(0,0,65,0,2*math.pi);c.fill()
        text('定格中',0,25,True)
    if shot_age is not None and 0<=shot_age<1.8:
        if shot_age<.22:
            c.set_source_rgba(1,1,1,.62*(1-shot_age/.22))
            c.rectangle(-width/(2*scale),-height/(2*scale),width/scale,height/scale);c.fill()
        else:
            alpha=min(1,(shot_age-.22)/.12,(1.8-shot_age)/.3)
            c.set_source_rgba(.025,.04,.055,.78*alpha)
            c.new_sub_path();c.arc(-83,-228,23,math.pi/2,3*math.pi/2)
            c.arc(83,-228,23,-math.pi/2,math.pi/2);c.close_path();c.fill()
            c.set_source_rgba(.64,.93,.85,alpha);c.set_line_width(2.5)
            c.move_to(-72,-229);c.line_to(-67,-224);c.line_to(-57,-234);c.stroke()
            text('拍摄完成',-228,19,True,alpha)
    if pickup_age is not None and 0<=pickup_age<8 and remaining is None and not waiting:
        alpha=min(1,pickup_age/.2,(8-pickup_age)/.6)
        c.set_source_rgba(.025,.04,.055,.88*alpha)
        c.new_sub_path();c.arc(-230,191,18,math.pi,1.5*math.pi);c.arc(230,191,18,1.5*math.pi,2*math.pi)
        c.arc(230,241,18,0,.5*math.pi);c.arc(-230,241,18,.5*math.pi,math.pi);c.close_path();c.fill()
        text('请到打印机处领取纪念报纸',202,26,True,alpha)
        text('报纸已提交打印，请稍候领取',236,16,False,.82*alpha)
    c.restore()
