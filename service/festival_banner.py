"""School festival header and camera attention cue, rendered without web views."""
import math
import gi
gi.require_version('Pango','1.0');gi.require_version('PangoCairo','1.0');gi.require_version('Gdk','3.0')
from gi.repository import Pango,PangoCairo,Gdk

def draw_banner(c,width,height,emblem=None,remaining=None,now=0):
    c.save();c.rectangle(0,0,width,height);c.clip()
    c.set_source_rgb(.045,.075,.095);c.paint()
    c.set_source_rgba(.58,.91,.82,.75);c.rectangle(0,height-2,width,2);c.fill()
    scale=min(width/1280,height/130)
    def label(value,x,y,size,bold=False,align='left',color=(1,1,1)):
        layout=PangoCairo.create_layout(c);font=Pango.FontDescription('Microsoft YaHei')
        font.set_absolute_size(size*scale*Pango.SCALE)
        if bold:font.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(font);layout.set_text(value,-1)
        w,h=layout.get_pixel_size();c.set_source_rgb(*color)
        c.move_to(x-(w/2 if align=='center' else w if align=='right' else 0),y-h/2);PangoCairo.show_layout(c,layout)
    logo=min(height*.70,110*scale);margin=28*scale
    if emblem:
        ratio=min(logo/emblem.get_width(),logo/emblem.get_height())
        c.save();c.translate(margin,(height-logo)/2);c.scale(ratio,ratio)
        Gdk.cairo_set_source_pixbuf(c,emblem,0,0);c.paint();c.restore()
    if remaining is not None:
        cx=width/2;cy=height*.49
        label('看向这里',cx,cy,39,True,'center')
        label('看向屏幕上方的摄像头',cx,height*.82,17,False,'center',(.67,.81,.80))
        c.set_source_rgb(.64,.93,.85);c.set_line_width(max(2,4*scale))
        for side in [-1,1]:
            x=cx+side*48*scale;y=height*.10+math.sin(now*6)*3*scale
            sx=cx+side*190*scale;sy=height*.65
            dx,dy=x-sx,y-sy;length=max(1,math.hypot(dx,dy));ux,uy=dx/length,dy/length
            c.move_to(sx,sy);c.line_to(x,y)
            c.move_to(x-ux*18*scale-uy*10*scale,y-uy*18*scale+ux*10*scale)
            c.line_to(x,y);c.line_to(x-ux*18*scale+uy*10*scale,y-uy*18*scale-ux*10*scale)
        c.stroke()
    else:
        x=margin+logo+24*scale
        label('北京市第六十五中学 · 2026年校园科技节',x,height*.23,21,True,color=(.68,.86,.82))
        label('做中学科学  实践促创新',x,height*.53,37,True)
        label('漫像时刻 — AI 动漫拍报机',x,height*.81,20)
        label('RDK S100',width-margin,height*.43,25,True,'right',(.64,.93,.85))
        label('实时动漫 · 手势拍照 · 纪念报纸',width-margin,height*.70,13,False,'right',(.72,.79,.81))
    c.restore()
