"""Two independent Python interpreters, at most one main BPU chain in flight.

The next latest camera frame starts when the previous frame reaches its CPU
tail. No frame batching, temporal reuse, or unbounded input/output queue.
"""
import multiprocessing as mp
import queue
import time
from pathlib import Path


def render_worker(slot, tasks, events):
    import sys
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'vendor'))
    import cv2
    from board_engine import BoardCamera
    camera = BoardCamera()
    camera.scene_size = 960
    events.put(('init', slot))
    while True:
        task = tasks.get()
        if task is None:
            return
        seq, frame, submitted = task
        signaled = False

        def ready():
            nonlocal signaled
            if not signaled:
                events.put(('stage', slot, seq))
                signaled = True

        camera.on_bpu_chain_done = ready
        try:
            scale = min(1, 1280 / max(frame.shape[:2]))
            small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
            begin = time.perf_counter()
            rgb = camera.render(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
            processing_ms = (time.perf_counter() - begin) * 1000
            rgb = cv2.flip(rgb, 1)
            metrics = {
                'processing_ms': processing_ms,
                'latency_ms': (time.perf_counter() - submitted) * 1000,
                'faces': int(camera.last_face_stats.get('refined', 0)),
                'detected_faces': int(camera.last_face_stats.get('detected', 0)),
                'capture_sequence': seq,
            }
            ready()
            events.put(('done', slot, seq, rgb, metrics))
        except Exception as exc:
            ready()
            events.put(('error', slot, seq, repr(exc)))


def run_pipeline(latest, running):
    """Yield ordered completed frames; latest() returns (camera_sequence, BGR)."""
    ctx = mp.get_context('spawn')
    events = ctx.Queue(maxsize=8)
    tasks = [ctx.Queue(maxsize=1) for _ in range(2)]
    workers = [ctx.Process(target=render_worker, args=(i, tasks[i], events), daemon=True) for i in range(2)]
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
                    tasks[next_slot].put((seq, frame, time.perf_counter()))
                    busy.add(next_slot)
                    next_slot = 1 - next_slot
                    can_submit = False
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
