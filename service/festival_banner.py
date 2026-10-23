"""School festival header and camera attention cue, rendered without web views."""
import math
import gi
gi.require_version('Pango','1.0');gi.require_version('PangoCairo','1.0');gi.require_version('Gdk','3.0')
from gi.repository import Pango,PangoCairo,Gdk

MESSAGES=(
    ('比出 ✌，3 秒后自动拍照','看见倒计时后，可以放下手势'),
    ('让此刻，成为动漫主角','看向上方镜头，留下你的科技节瞬间'),
    ('把科技节的快乐带回家','拍照后自动生成专属纪念报纸'),
    ('一个手势，定格你的精彩','举起食指和中指，试试 V 字手势'),
)

def draw_banner(c,width,height,emblem=None,remaining=None,now=0):
    c.save();c.rectangle(0,0,width,height);c.clip()
    c.set_source_rgb(.045,.075,.095);c.paint()
    c.set_source_rgba(.58,.91,.82,.75);c.rectangle(0,height-2,width,2);c.fill()
    scale=min(width/1280,height/130)
    def label(value,x,y,size,bold=False,align='left',color=(1,1,1),max_width=None,outline=0):
        layout=PangoCairo.create_layout(c);font=Pango.FontDescription('Microsoft YaHei')
        font.set_absolute_size(size*scale*Pango.SCALE)
        if bold:font.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(font);layout.set_text(value,-1)
        w,h=layout.get_pixel_size()
        if max_width is not None and w>max_width:
            font.set_absolute_size(size*scale*Pango.SCALE*max_width/w)
            layout.set_font_description(font);w,h=layout.get_pixel_size()
        c.set_source_rgb(*color)
        c.move_to(x-(w/2 if align=='center' else w if align=='right' else 0),y-h/2)
        if outline:
            c.save();PangoCairo.layout_path(c,layout);c.set_line_width(outline*scale)
            c.set_line_join(1);c.stroke_preserve();c.fill();c.restore()
        else:PangoCairo.show_layout(c,layout)
        return w
    logo=min(height*.70,110*scale);margin=28*scale
    if emblem:
        ratio=min(logo/emblem.get_width(),logo/emblem.get_height())
        c.save();c.translate(margin,(height-logo)/2);c.scale(ratio,ratio)
        Gdk.cairo_set_source_pixbuf(c,emblem,0,0);c.paint();c.restore()
    if remaining is not None:
        cx=width/2;cy=height*.49
        wave=math.sin(now*6)
        c.save();c.translate(cx+16*scale*wave,cy+3*scale*math.sin(now*8));c.rotate(.075*wave)
        label('看向这里',0,0,39,True,'center',outline=2.5);c.restore()
        label('看向屏幕上方的摄像头',cx,height*.82,17,False,'center',(.67,.81,.80))
        c.set_source_rgb(.64,.93,.85);c.set_line_width(max(4,8*scale))
        c.set_line_cap(1);c.set_line_join(1)
        for side in [-1,1]:
            x=cx+side*48*scale+12*scale*wave;y=max(10*scale,height*.10+math.sin(now*7)*14*scale)
            sx=cx+side*190*scale+14*scale*wave;sy=height*.65+8*scale*wave
            dx,dy=x-sx,y-sy;length=max(1,math.hypot(dx,dy));ux,uy=dx/length,dy/length
            c.move_to(sx,sy);c.line_to(x,y)
            c.move_to(x-ux*18*scale-uy*10*scale,y-uy*18*scale+ux*10*scale)
            c.line_to(x,y);c.line_to(x-ux*18*scale+uy*10*scale,y-uy*18*scale-ux*10*scale)
        c.stroke()
    else:
        x=margin+logo+24*scale
        school_width=label('北京市第六十五中学 · 2026年校园科技节',x,height*.23,21,True,color=(.68,.86,.82))
        theme_width=label('做中学科学  实践促创新',x,height*.53,37,True)
        name_width=label('漫像时刻 — AI 动漫拍报机',x,height*.81,20)
        right_width=max(1,width-margin-x-max(school_width,theme_width,name_width)-32*scale)
        index=int(now/6)%len(MESSAGES);headline,detail=MESSAGES[index]
        label(headline,width-margin,height*.36,46,True,'right',(.64,.93,.85),max_width=right_width)
        label(detail,width-margin,height*.69,28,False,'right',(.78,.84,.85),max_width=right_width)
        for i in range(len(MESSAGES)):
            c.set_source_rgba(.64,.93,.85,1 if i==index else .22)
            c.arc(width-margin-(len(MESSAGES)-1-i)*13*scale,height*.85,2.5*scale,0,2*math.pi);c.fill()
    c.restore()
