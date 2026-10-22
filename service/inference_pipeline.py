"""Two independent Python interpreters, at most two fresh frames in flight.

The next latest frame starts after the previous last-face structure stage.
This fills inter-model CPU gaps without unbounded BPU task accumulation.
"""
import multiprocessing as mp
import queue
import time
from pathlib import Path


def render_worker(slot, tasks, events, release_stage='structure'):
    import sys
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'vendor'))
    import cv2
    from board_engine import BoardCamera
    from display_settings import DEFAULT_SETTINGS, prepare_frame, output_dimensions
    camera = BoardCamera()
    camera.scene_size = max(DEFAULT_SETTINGS['width'],DEFAULT_SETTINGS['height'])
    if release_stage in ('structure', 'anime'):
        key = 'portrait_v2_512' if release_stage == 'structure' else 'portrait_anime'
        original_runner = camera.trt[key]

        def signal_after_stage(value):
            result = original_runner(value)
            if getattr(camera, '_remaining_faces', -1) == 0:
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
                scale = min(1, 1280 / max(frame.shape[:2]))
                small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
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


def run_pipeline(latest, running, release_stage='structure', configuration=None):
    """Yield ordered completed frames; latest() returns (camera_sequence, BGR)."""
    ctx = mp.get_context('spawn')
    events = ctx.Queue(maxsize=8)
    tasks = [ctx.Queue(maxsize=1) for _ in range(2)]
    if release_stage not in ('parser', 'anime', 'structure', 'ungated'):
        raise ValueError('Unsupported BPU release stage')
    workers = [ctx.Process(target=render_worker, args=(i, tasks[i], events, release_stage), daemon=True) for i in range(2)]
    try:
        for worker in workers:
            worker.start()
        initialized = set()
        deadline = time.monotonic() + 90
        while running() and len(initialized) < 2:
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
        next_slot = 0
        can_submit = True
        previous = displayed = -1
        progress = time.monotonic()
        while running():
            if any(not p.is_alive() for p in workers):
                raise RuntimeError('BPU worker exited')
            if busy and time.monotonic() - progress > 30:
                raise RuntimeError('BPU worker stalled')
            if can_submit and next_slot not in busy:
                seq, frame = latest()
                if frame is not None and seq != previous:
                    previous = seq
                    settings = dict(configuration()) if configuration is not None else None
                    tasks[next_slot].put((seq, frame, time.perf_counter(), settings))
                    busy.add(next_slot)
                    next_slot = 1 - next_slot
                    can_submit = release_stage == 'ungated'
                    progress = time.monotonic()
            try:
                event = events.get(timeout=.01)
            except queue.Empty:
                continue
            progress = time.monotonic()
            kind, slot, seq = event[:3]
            if kind == 'stage':
                can_submit = True
            elif kind in ('done', 'error'):
                busy.discard(slot)
                if kind == 'error':
                    print('INFERENCE_WORKER', event[3], flush=True)
                elif seq > displayed:
                    displayed = seq
                    yield event[3], event[4]
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
        for worker in workers:
            if worker.pid is not None:
                worker.join(timeout=3)
        events.close()
        for task in tasks:
            task.close()
