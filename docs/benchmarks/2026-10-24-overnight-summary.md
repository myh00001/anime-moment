# Overnight validation, 2026-10-24

The retained version keeps 1920×1080 output, the existing anime models and
style, camera-original reporting, photo capture, A5 PDF generation, printing,
gallery, fullscreen, mirror and rotation options. Manual close still leaves
the app closed. No extra test pages were printed.

## Retained improvements

- The 500M vision model uses an original-derived upper-body view; unsupported
  or uncertain clothing claims fall back to neutral copy. A clipped face
  without enough visible upper body does not trigger a clothing description.
- A deterministic optional vision decoder preserved jacket descriptions on
  seven saved originals, compared with five correct, one neutral and one
  incorrect shirt description from the sampled decoder. This is a small
  same-person fixture, not a general accuracy estimate.
- Exact-model CPU gesture acceleration improved no-face FPS by about 1.5–2.2%
  and palm scanning by 17–18% in earlier paired live trials. Thresholds and
  global search windows are unchanged.
- Writer startup and cold prompt prefill overlap vision work. A paired saved
  original comparison reduced cold report-plus-PDF time from 11.572 to 9.122
  seconds before the later environment-cache change. These times exclude
  countdown and printer output.
- Direct embedding of the existing RGB JPEG preserved rendered PDF pixels
  while reducing warm PDF generation by about 0.55 seconds in two fixtures.
- Successful TROS environment reuse reduced a warm report-plus-PDF comparison
  from 7.233 to 6.781 seconds. These gains cannot simply be added across
  trials because workloads and overlapping stages differ.

The full local suite passed 74 tests. Live PDF-only integration verified the
same capture's original source, frozen preview during generation, PDF output
and exact restoration of user settings. No person was visible in those live
checks; positive-person reporting used saved originals.

## Rejected candidates and remaining limits

Hardware JPEG decoding and fast CPU DCT changed pixels. Shared-memory image
transport had earlier face-scene regressions. Lowering the gesture thread's
CPU priority slightly increased FPS but reduced scanning frequency. These
candidates were not retained.

The existing face structure model remains a major latency component. This
night did not establish 30 FPS, full BPU utilization, or a large improvement in
face-scene throughput. The final continuous live soak contains no detected
faces and must not be presented as a face FPS result.

The final aggregate measurements are in
[`2026-10-24-final-soak.json`](2026-10-24-final-soak.json). Camera images, PDFs,
model weights, credentials, raw reports and private logs remain off GitHub.
