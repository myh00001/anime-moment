"""Small monochrome vector weather symbols for sharp printed output."""
import math

def draw_weather_icon(canvas,x,y,size,code=None):
    canvas.saveState();canvas.translate(x,y);canvas.scale(size,size)
    canvas.setStrokeColorRGB(0,0,0);canvas.setFillColorRGB(1,1,1);canvas.setLineWidth(.045)
    canvas.setLineCap(1);canvas.setLineJoin(1)
    def sun(cx,cy,r):
        for n in range(8):
            angle=n*math.pi/4
            canvas.line(cx+math.cos(angle)*r*1.4,cy+math.sin(angle)*r*1.4,cx+math.cos(angle)*r*1.9,cy+math.sin(angle)*r*1.9)
        canvas.circle(cx,cy,r,fill=1,stroke=1)
    def cloud():
        p=canvas.beginPath();p.moveTo(.2,.37)
        p.curveTo(-.01,.37,-.01,.69,.2,.7);p.curveTo(.22,.96,.58,.99,.68,.77)
        p.curveTo(.9,.88,1.09,.49,.84,.38);p.lineTo(.2,.37);p.close()
        canvas.drawPath(p,fill=1,stroke=1)
    if code==0:sun(.5,.5,.21)
    elif code in (1,2):sun(.26,.72,.13);cloud()
    elif code in (3,45,48):
        cloud()
        if code in (45,48):
            for yy in (.23,.1):canvas.line(.12,yy,.85,yy)
    elif code in (51,53,55,56,57,61,63,65,66,67,80,81,82):
        cloud()
        for xx in (.3,.52,.74):canvas.line(xx,.25,xx-.07,.07)
    elif code in (71,73,75,77,85,86):
        cloud()
        for xx in (.3,.66):
            for angle in (0,math.pi/3,2*math.pi/3):
                dx,dy=.09*math.cos(angle),.09*math.sin(angle);canvas.line(xx-dx,.15-dy,xx+dx,.15+dy)
    elif code in (95,96,99):
        cloud();p=canvas.beginPath();p.moveTo(.55,.34);p.lineTo(.4,.17);p.lineTo(.56,.17);p.lineTo(.44,.01);canvas.drawPath(p)
    else:
        cloud();canvas.setFillColorRGB(0,0,0);canvas.circle(.5,.16,.025,fill=1,stroke=0)
    canvas.restoreState()
