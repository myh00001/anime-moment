import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from io import BytesIO
import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, Response
import uvicorn
from board_engine import BoardCamera, ROOT

worker = ThreadPoolExecutor(max_workers=1)
busy = False


@asynccontextmanager
async def lifespan(api):
    global camera
    camera = await asyncio.get_running_loop().run_in_executor(worker, BoardCamera)
    yield
    worker.shutdown(wait=False)


api = FastAPI(lifespan=lifespan)


@api.get('/')
def index():
    return FileResponse(ROOT / 'camera.html')


@api.get('/health')
def health():
    return {'ready': True, 'backend': 'S100 BPU', 'native_model_size': [640, 360]}


@api.post('/camera-info')
async def camera_info(request: Request):
    # Device information is acknowledged without retaining camera images.
    await request.json()
    return {'ok': True}


def process(data, output_edge):
    start = time.perf_counter()
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 40000000:
            raise ValueError('Image too large')
        rgb = np.asarray(image.convert('RGB'))
    camera.scene_size = output_edge
    out = camera.render(rgb)
    ok, encoded = cv2.imencode('.jpg', cv2.cvtColor(out, cv2.COLOR_RGB2BGR),
                               [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise ValueError('JPEG encoding failed')
    return encoded.tobytes(), (time.perf_counter() - start) * 1000, camera.last_face_stats


@api.post('/frame')
async def frame(request: Request):
    global busy
    if busy:
        raise HTTPException(429, 'Processing latest frame; skip queued frames')
    try:
        edge = int(request.query_params.get('output_edge', '640'))
        if not 320 <= edge <= 1920:
            raise ValueError()
    except ValueError:
        raise HTTPException(400, 'Output long edge must be 320–1920 pixels')
    busy = True
    try:
        data = await request.body()
        if len(data) > 32000000:
            raise HTTPException(413, 'Frame too large')
        payload, ms, stats = await asyncio.get_running_loop().run_in_executor(worker, process, data, edge)
        return Response(payload, media_type='image/jpeg', headers={
            'X-Processing-Ms': f'{ms:.1f}',
            'X-Faces-Refined': str(stats.get('refined', 0)),
            'X-Faces-Stable': str(stats.get('stable_faces', 0)),
            'X-Faces-Tracked': '0',
            'X-Input-Sharpness': str(stats.get('input_sharpness', 0)),
            'X-Inference-Backend': 'S100 BPU', 'Cache-Control': 'no-store'})
    finally:
        busy = False


if __name__ == '__main__':
    uvicorn.run(api, host='127.0.0.1', port=7860)
