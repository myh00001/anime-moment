"""Bridge brief detector misses with checked optical flow, never cached faces."""
import time
import cv2
import numpy as np

class FaceContinuity:
    def __init__(self, max_misses=2, max_gap=.8):
        self.max_misses=max_misses
        self.max_gap=max_gap
        self.gray=None
        self.tracks=[]

    def _predict(self, gray, track):
        if self.gray is None or self.gray.shape!=gray.shape:
            return None
        points=track['points']
        lo,hi=points.min(axis=0),points.max(axis=0)
        span=np.maximum(hi-lo,12)
        mask=np.zeros_like(gray)
        x0,y0=np.maximum(lo-span*.6,0).astype(int)
        x1,y1=np.minimum(hi+span*.6,[gray.shape[1],gray.shape[0]]).astype(int)
        mask[y0:y1,x0:x1]=255
        corners=cv2.goodFeaturesToTrack(self.gray,60,.015,4,mask=mask,blockSize=5)
        if corners is None or len(corners)<8:
            return None
        forward,ok,_=cv2.calcOpticalFlowPyrLK(self.gray,gray,corners,None,winSize=(21,21),maxLevel=3)
        if forward is None: return None
        backward,back_ok,_=cv2.calcOpticalFlowPyrLK(gray,self.gray,forward,None,winSize=(21,21),maxLevel=3)
        if backward is None: return None
        valid=(ok.ravel()!=0)&(back_ok.ravel()!=0)&(np.linalg.norm(backward-corners,axis=2).ravel()<1.2)
        if valid.sum()<8: return None
        transform,inliers=cv2.estimateAffinePartial2D(corners[valid,0],forward[valid,0],method=cv2.RANSAC,ransacReprojThreshold=1.5)
        if transform is None or inliers.mean()<.65: return None
        scale=np.linalg.norm(transform[:,0])
        if not .75<scale<1.3: return None
        predicted=cv2.transform(points[None].astype(np.float32),transform)[0]
        if np.linalg.norm(predicted.mean(axis=0)-points.mean(axis=0))>max(span)*.9:
            return None
        if np.any(predicted<0) or np.any(predicted[:,0]>=gray.shape[1]) or np.any(predicted[:,1]>=gray.shape[0]):
            return None
        return dict(points=predicted,misses=track['misses']+1,last_seen=track['last_seen'])

    def update(self, gray, detections, now=None):
        now=time.monotonic() if now is None else now
        candidates=[]
        for track in self.tracks:
            if track['misses']<self.max_misses and now-track['last_seen']<=self.max_gap:
                candidate=self._predict(gray,track)
                if candidate is not None: candidates.append(candidate)
        tracks=[]
        for points in detections:
            points=np.asarray(points,np.float32)
            center=points.mean(axis=0)
            width=max(float(np.ptp(points[:,0])),12)
            if candidates:
                distances=[np.linalg.norm(center-t['points'].mean(axis=0)) for t in candidates]
                best=int(np.argmin(distances))
                if distances[best]<width*.9: candidates.pop(best)
            tracks.append(dict(points=points,misses=0,last_seen=now))
        tracked=max(0,min(3-len(tracks),len(candidates)))
        tracks.extend(candidates[:tracked])
        self.tracks=tracks
        self.gray=gray.copy()
        return [t['points'] for t in tracks],tracked
