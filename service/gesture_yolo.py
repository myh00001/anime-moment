"""Static-shape HaGRID YOLOv10 one-to-one head preprocessing and decoding."""
import numpy as np
LABELS=['grabbing','grip','holy','point','call','three3','timeout','xsign','hand_heart','hand_heart2','little_finger','middle_finger','take_picture','dislike','fist','four','like','mute','ok','one','palm','peace','peace_inverted','rock','stop','stop_inverted','three','three2','two_up','two_up_inverted','three_gun','thumb_index','thumb_index2','no_gesture']

def prepare(image,size=640):
 import cv2
 h,w=image.shape[:2];gain=min(size/w,size/h);nw,nh=round(w*gain),round(h*gain);x,y=(size-nw)//2,(size-nh)//2
 out=np.full((size,size,3),114,np.uint8);out[y:y+nh,x:x+nw]=cv2.resize(image,(nw,nh))
 return np.ascontiguousarray(out[:,:,::-1].transpose(2,0,1)[None]).astype(np.float32)/255,(gain,x,y,w,h)

def decode(outputs,geometry,threshold=.5):
 boxes=[];scores=[];anchors=[];strides=[]
 for stride in [8,16,32]:
  reg=np.asarray(outputs[f'boxes_s{stride}']);cls=np.asarray(outputs[f'classes_s{stride}'])
  if reg.shape[1]!=64:reg=reg.transpose(0,3,1,2)
  if cls.shape[1]!=34:cls=cls.transpose(0,3,1,2)
  h,w=reg.shape[2:];boxes.append(reg[0].reshape(64,-1).T);scores.append(cls[0].reshape(34,-1).T)
  yy,xx=np.mgrid[:h,:w];anchors.append(np.stack((xx.ravel()+.5,yy.ravel()+.5),1));strides.append(np.full(h*w,stride))
 logits=np.concatenate(scores);prob=1/(1+np.exp(-np.clip(logits,-80,80)))
 # A gesture must win against all competing classes at its anchor.
 winners=prob.argmax(1);cells_above=np.flatnonzero(prob[np.arange(len(prob)),winners]>=threshold)
 indices=cells_above*34+winners[cells_above]
 if not len(indices):return []
 if len(indices)>300:indices=indices[np.argpartition(prob.ravel()[indices],-300)[-300:]]
 indices=indices[np.argsort(-prob.ravel()[indices])];cells=indices//34;classes=indices%34
 dist=np.concatenate(boxes)[cells].reshape(-1,4,16);dist-=dist.max(2,keepdims=True);dist=np.exp(dist);dist=(dist*np.arange(16)).sum(2)/dist.sum(2)
 anchor=np.concatenate(anchors)[cells];step=np.concatenate(strides)[cells,None];xy=np.concatenate((anchor-dist[:,:2],anchor+dist[:,2:]),1)*step
 gain,x,y,w,h=geometry;xy=(xy-np.array([x,y,x,y]))/gain;xy=np.clip(xy,0,[w,h,w,h])
 return [{'class_id':int(k),'class':LABELS[k],'score':float(prob[cell,k]),'box':box.tolist()} for k,cell,box in zip(classes,cells,xy)]


class BpuGestureDetector:
 """Direct image-to-gesture inference, without finger landmark estimation."""
 def __init__(self,path,size=384,threshold=.5):
  from hbm_runtime import HB_HBMRuntime
  self.runtime=HB_HBMRuntime(str(path));self.name=self.runtime.model_names[0]
  self.size=size;self.threshold=threshold;self.region=None;self.tile_index=0
 def infer_view(self,image):
  tensor,geometry=prepare(image,self.size)
  out=self.runtime.run({'images':tensor},model_name=self.name)[self.name]
  return decode(out,geometry,self.threshold)
 def detect(self,image):
  h,w=image.shape[:2];regions=[]
  if self.region is not None:
   x1,y1,x2,y2=self.region
   if 0<=x1<x2<=w and 0<=y1<y2<=h:regions.append(self.region)
   else:self.region=None
  regions.append(None)
  # Keep small distant hands readable: scan overlapping native-resolution tiles.
  side=min(640,max(w,h));step=max(1,int(side*.75))
  xs=list(range(0,max(1,w-side+1),step));ys=list(range(0,max(1,h-side+1),step))
  if xs[-1]!=max(0,w-side):xs.append(max(0,w-side))
  if ys[-1]!=max(0,h-side):ys.append(max(0,h-side))
  tiles=[(x,y,min(w,x+side),min(h,y+side)) for y in ys for x in xs]
  if len(tiles)>1:regions.append(tiles[self.tile_index%len(tiles)]);self.tile_index+=1
  seen=set()
  for region in regions:
   if region in seen:continue
   seen.add(region)
   if region is None:view=image;dx=dy=0
   else:
    dx,dy,x2,y2=region;view=image[dy:y2,dx:x2]
   detections=self.infer_view(view)
   for row in detections:
    if row['class_id'] not in (21,22):continue
    box=np.array(row['box'])+np.array([dx,dy,dx,dy]);cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
    half=max(192,float(max(box[2]-box[0],box[3]-box[1]))*2)
    self.region=(max(0,int(cx-half)),max(0,int(cy-half)),min(w,int(cx+half)),min(h,int(cy+half)))
    return True
  self.region=None;return False
