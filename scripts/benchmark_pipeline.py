"""Replay local frames through the real pipeline; never save image pixels.

Stop the display service before measuring, and restart it after the command.
Use identical inputs/settings to compare revisions. Requires board dependencies.
"""
import argparse
import importlib
import json
from pathlib import Path
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--service-dir', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'service')
    parser.add_argument('--pipeline', default='inference_pipeline')
    parser.add_argument('--reference-engine', default='board_engine')
    parser.add_argument('--edge', type=int, default=1920)
    parser.add_argument('--frames', type=int, default=96)
    parser.add_argument('--warmup', type=int, default=8)
    parser.add_argument('--release-stage', default='structure',
                        choices=['structure', 'anime', 'parser', 'scene', 'ungated'])
    parser.add_argument('--max-pixel-error', type=int, default=0)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.frames < args.warmup + 3 or args.warmup < 0:
        parser.error('frames must exceed warmup by at least three')
    if not 320 <= args.edge <= 1920 or args.edge % 4:
        parser.error('edge must be a multiple of four from 320 to 1920')
    sys.path[:0] = [str(args.service_dir), str(args.service_dir / 'vendor')]
    import cv2
    import numpy as np
    from display_settings import prepare_frame
    from resource_monitor import ResourceMonitor

    engine = importlib.import_module(args.reference_engine).BoardCamera()
    run = importlib.import_module(args.pipeline).run_pipeline
    settings = dict(width=args.edge, height=max(4, args.edge // 16 * 9 // 4 * 4),
                    rotation=0, mirror=True)
    engine.scene_size = args.edge
    frames, expected = [], []
    for path in args.inputs:
        frame = cv2.imread(str(path))
        if frame is None:
            raise ValueError('Cannot decode an input image')
        frames.append(frame)
        rgb = cv2.cvtColor(prepare_frame(frame, settings), cv2.COLOR_BGR2RGB)
        expected.append(cv2.flip(engine.render(rgb), 1))
    counter = -1

    def latest():
        nonlocal counter
        counter += 1
        return counter, frames[counter % len(frames)]

    samples, records, stamps = [], [], []
    stop = threading.Event()

    def monitor():
        reader = ResourceMonitor()
        while not stop.wait(.5):
            samples.append((time.perf_counter(), reader.sample()))

    thread = threading.Thread(target=monitor)
    thread.start()
    pipeline = run(latest, lambda: True, release_stage=args.release_stage,
                   configuration=lambda: settings)
    try:
        for output, metrics in pipeline:
            now = time.perf_counter()
            reference = expected[metrics['capture_sequence'] % len(frames)]
            if output.shape != reference.shape:
                raise ValueError('Pipeline and reference output shapes differ')
            error = np.abs(output.astype(np.int16) - reference)
            records.append(dict(metrics, max_pixel_error=int(error.max()),
                                pixel_mae=float(error.mean())))
            stamps.append(now)
            if len(records) >= args.frames:
                break
    finally:
        pipeline.close()
        stop.set()
        thread.join()
    steady = records[args.warmup:]
    ratios = [value for timestamp, sample in samples
              if stamps[args.warmup] <= timestamp <= stamps[-1]
              for value in sample.get('bpu_percent', {}).values()]
    report = dict(
        frames=len(records), warmup=args.warmup, settings=settings,
        input_count=len(frames),
        input_dimensions=[[f.shape[1], f.shape[0]] for f in frames],
        pipeline=args.pipeline, release_stage=args.release_stage,
        fps=(len(steady) - 1) / (stamps[-1] - stamps[args.warmup]),
        latency_ms=float(np.mean([r['latency_ms'] for r in steady])),
        latency_p95_ms=float(np.percentile([r['latency_ms'] for r in steady], 95)),
        bpu_mean_percent=float(np.mean(ratios)) if ratios else None,
        max_pixel_error=max(r['max_pixel_error'] for r in records),
        pixel_mae_max=max(r['pixel_mae'] for r in records),
        faces=sorted(set(r['faces'] for r in records)),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if report['max_pixel_error'] > args.max_pixel_error:
        raise SystemExit('Pixel difference exceeds the permitted limit')


if __name__ == '__main__':
    main()
