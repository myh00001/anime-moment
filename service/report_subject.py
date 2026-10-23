"""Locate a visible subject once per photograph, without changing saved framing."""
from pathlib import Path


def subject_box(faces,width,height,scale):
    """Use the largest detected face to include its head and upper body."""
    if faces is None or len(faces)==0:return None
    face=max(faces,key=lambda f:float(f[2])*float(f[3]))
    x,y,w,h=[float(v)/scale for v in face[:4]]
    if w<12 or h<12:return None
    center=x+w/2
    box=(max(0,int(center-w*2.1)),max(0,int(y-h*.35)),
         min(width,int(center+w*2.1)),min(height,int(y+h*4.8)))
    return box if box[2]-box[0]>=12 and box[3]-box[1]>=12 else None


def prepare_subject(photo,destination,size,root):
    import cv2
    import numpy as np
    cv2.setNumThreads(1)
    image=cv2.imread(str(photo))
    if image is None:raise ValueError('Original camera image cannot be read')
    height,width=image.shape[:2];scale=640/max(width,height)
    w,h=round(width*scale),round(height*scale)
    canvas=np.zeros((640,640,3),np.uint8)
    canvas[:h,:w]=cv2.resize(image,(w,h),interpolation=cv2.INTER_AREA)
    detector=cv2.FaceDetectorYN.create(str(Path(root)/'models/face_detection_yunet_2023mar.onnx'),
        '',(640,640),.65,.3,2000)
    _,faces=detector.detect(canvas)
    box=subject_box(faces,width,height,scale)
    if box is None:return {'subject_visible':False,'faces':0}
    x0,y0,x1,y1=box
    cropped=cv2.resize(image[y0:y1,x0:x1],(size,size),interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(str(destination),cropped):raise OSError('Cannot prepare original subject view')
    return {'subject_visible':True,'faces':len(faces),'source_box':list(box)}
