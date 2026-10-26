"""N independent Python interpreters, at most K main BPU chains in flight.

Same scheduling idea as the original (latest frame only, bounded in-flight work,
ordered output), generalised:
  RAC_WORKERS   number of worker processes (default 2)
  RAC_INFLIGHT  max frames admitted before the previous one reached its CPU tail
                (default 2 = measured W2/INF2 path; 1 restores the single-chain gate)
  RAC_PRESCALE  resize to <=1280 in the parent before pickling (identical math,
                less IPC for 1080p). The full camera frame is still kept for the
                festival original photo.
  RAC_THREADS   if set, pin cv2 threads in each worker; otherwise the camera
                keeps its adaptive 6/3 pool.
"""
import multiprocessing as mp
import os
import queue
import time
from pathlib import Path

WORKERS = max(1, int(os.environ.get('RAC_WORKERS', '2')))
INFLIGHT = max(1, int(os.environ.get('RAC_INFLIGHT', '2')))
PRESCALE = os.environ.get('RAC_PRESCALE', '1') == '1'


def prescale(frame):
    import cv2
    scale = min(1, 1280 / max(frame.shape[:2]))
    return cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame


def render_worker(slot, tasks, events, release_stage='structure'):
    import sys
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'vendor'))
    import cv2
    from board_engine import BoardCamera
    from display_settings import DEFAULT_SETTINGS, prepare_frame, output_dimensions
    camera = BoardCamera()
    camera.scene_size = max(DEFAULT_SETTINGS['width'], DEFAULT_SETTINGS['height'])
    if release_stage in ('structure', 'anime', 'scene'):
        key = {'structure': 'portrait_v2_512', 'anime': 'portrait_anime', 'scene': 'scene'}[release_stage]
        # RAC_FACE=0 does not load portrait models. Scene release still wraps scene;
        # the no-face path signals on_bpu_chain_done itself when that key is absent.
        if key in camera.trt:
            original_runner = camera.trt[key]

            def signal_after_stage(value):
                result = original_runner(value)
                if release_stage == 'scene' or getattr(camera, '_remaining_faces', -1) == 0:
                    camera.on_bpu_chain_done()
                return result

            camera.trt[key] = signal_after_stage
    events.put(('init', slot))
    while True:
        task = tasks.get()
        if task is None:
            return
        seq, frame, submitted, settings = task
        signaled = False

        def ready():
            nonlocal signaled
            if not signaled:
                events.put(('stage', slot, seq))
                signaled = True

        camera.on_bpu_chain_done = ready
        try:
            if settings is None:
                small = prescale(frame)
            else:
                small = prepare_frame(frame, settings)
                camera.scene_size = max(settings['width'], settings['height'])
            begin = time.perf_counter()
            rgb = camera.render(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
            processing_ms = (time.perf_counter() - begin) * 1000
            if settings is not None:
                size = output_dimensions(small.shape[1], small.shape[0], max(settings['width'], settings['height']))
                if (rgb.shape[1], rgb.shape[0]) != size:
                    rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_CUBIC)
            if settings is None or settings['mirror']:
                rgb = cv2.flip(rgb, 1)
            metrics = {
                'processing_ms': processing_ms,
                'latency_ms': (time.perf_counter() - submitted) * 1000,
                'faces': int(camera.last_face_stats.get('refined', 0)),
                'detected_faces': int(camera.last_face_stats.get('detected', 0)),
                'capture_sequence': seq,
                'settings': settings,
                'release_stage': release_stage,
            }
            ready()
            events.put(('done', slot, seq, rgb, metrics))
        except Exception as exc:
            ready()
            events.put(('error', slot, seq, repr(exc)))


def _pipeline_session(latest, running, release_stage=None, configuration=None, paused=lambda: False, idle=lambda value: None):
    """Yield ordered completed frames; latest() returns (camera_sequence, BGR)."""
    if release_stage is None:
        from native_math import AVAILABLE
        release_stage = 'scene' if AVAILABLE else 'structure'
    ctx = mp.get_context('spawn')
    events = ctx.Queue(maxsize=8 + 2 * WORKERS)
    tasks = [ctx.Queue(maxsize=1) for _ in range(WORKERS)]
    if release_stage not in ('parser', 'anime', 'structure', 'scene', 'ungated'):
        raise ValueError('Unsupported BPU release stage')
    workers = [ctx.Process(target=render_worker, args=(i, tasks[i], events, release_stage), daemon=True) for i in range(WORKERS)]
    limit = WORKERS if release_stage == 'ungated' else INFLIGHT
    try:
        for worker in workers:
            worker.start()
        initialized = set()
        deadline = time.monotonic() + 120
        while running() and len(initialized) < WORKERS:
            if time.monotonic() > deadline:
                raise RuntimeError('BPU workers did not initialize')
            if any(p.exitcode is not None for p in workers):
                raise RuntimeError('BPU worker exited during initialization')
            try:
                event = events.get(timeout=.1)
            except queue.Empty:
                continue
            if event[0] == 'init':
                initialized.add(event[1])
        busy = set()
        gated = set()
        originals = {}
        previous = displayed = -1
        progress = time.monotonic()
        while running():
            if any(not p.is_alive() for p in workers):
                raise RuntimeError('BPU worker exited')
            if busy and time.monotonic() - progress > 30:
                raise RuntimeError('BPU worker stalled')
            is_paused = paused()
            if is_paused and not busy:
                return
            idle(False)
            free = [s for s in range(WORKERS) if s not in busy]
            if not is_paused and free and len(gated) < limit:
                seq, frame = latest()
                if frame is not None and seq != previous:
                    previous = seq
                    originals[seq] = frame
                    settings = dict(configuration()) if configuration is not None else None
                    payload = prescale(frame) if PRESCALE else frame
                    slot = free[0]
                    tasks[slot].put((seq, payload, time.perf_counter(), settings))
                    busy.add(slot)
                    gated.add(slot)
                    progress = time.monotonic()
            try:
                event = events.get(timeout=.005)
            except queue.Empty:
                continue
            progress = time.monotonic()
            kind, slot, seq = event[:3]
            if kind == 'stage':
                gated.discard(slot)
            elif kind in ('done', 'error'):
                busy.discard(slot)
                gated.discard(slot)
                original = originals.pop(seq, None)
                if kind == 'error':
                    print('INFERENCE_WORKER', event[3], flush=True)
                elif seq > displayed:
                    displayed = seq
                    event[4]['original_bgr'] = original
                    yield event[3], event[4]
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
        for worker in workers:
            if worker.pid is not None:
                worker.join(timeout=3)
        idle(not any(worker.is_alive() for worker in workers))
        events.close()
        for task in tasks:
            task.close()


def run_pipeline(latest, running, release_stage=None, configuration=None, paused=lambda: False, idle=lambda value: None):
    """Release all render-model contexts while a photo report owns the BPU."""
    while running():
        while running() and paused():
            idle(True)
            time.sleep(.05)
        if not running():
            break
        idle(False)
        yield from _pipeline_session(latest, running, release_stage, configuration, paused, idle)
