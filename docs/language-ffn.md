# Experimental language FFN prefill on S100

This is a partial adaptation of the existing InternVL3-2B Q8 language decoder,
not a different image recognition model. The image encoder remains on the BPU.
Selected decoder SwiGLU FFNs for 128–256 input tokens use model-specific HBM
functions. Attention, RoPE, KV cache, short text prefill, final selected token
and autoregressive decoding remain on the CPU. The parallel Qwen3-0.6B writer
also remains on the CPU. Camera originals, prompts and image token count do
not change.

The feature is **off unless a validated `local-vlm/report-ffn.json` is installed**.
A missing or mismatched model, binary or worker digest selects the normal
runtime. A runtime failure shuts down the experiment and retries the same
original with the stable CPU language decoder and BPU image encoder. It does
not silently report that fallback as BPU FFN acceleration.

## Artifacts and preparation

Use the existing b11669 static build and its S100 embedding bridge. Run
`scripts/build_language_ffn_bridge.py --root SERVICE_DIRECTORY` to create an
isolated `local-vlm/ffn-bridge-runtime`; production sources, libraries and
binaries are not overwritten. An unrecognized Qwen2 source graph is rejected.

`scripts/export_language_ffn.py` dequantizes each installed Q8 GGUF layer and
exports its up/gate/down SwiGLU computation as ONNX Conv1x1 operations. The
experiment uses 256-token buckets and layers 0–26. Layer 27 receives the
selected final token and stays on CPU. Shorter eligible blocks are zero-padded
and sliced after inference. Export requires optional `gguf`, `onnx` and NumPy;
these development tools are not needed by normal camera operation.

Calibration inputs must come from the **same decoder**, after normalization,
using the native opt-in `S100_FFN_DUMP_DIR` hook. Such dumps contain private
image-derived features and must stay out of source control. Compile with the
S100 `nash-e` toolchain, one core, O0. The Conv and SiLU/product activation nodes
require INT16 in this experiment; default INT8 activations failed the numerical
quality check. INT16 activations do not make the entire model FP16 or INT16.
Keep original GGUF files, calibration data, ONNX, HBM and generated manifests
in private model directories.

Place validated HBM files at
`local-vlm/language-bpu-step1/ffn-models/ffnLAYER_t256.hbm`. Then run:

```sh
python3 scripts/setup_report_ffn.py --root SERVICE_DIRECTORY --layers 9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26
```

This copies the worker and writes a **candidate** manifest, without restarting
or enabling the camera experiment. Only after numerical, same-image report,
repeat-call and complete original-to-PDF checks pass, use `--enable` to install
the production manifest. Stop the camera before replacing an active worker.
The helper does not modify desktop startup, printer settings or service restart
policies. Disable with `FESTIVAL_GENERAL_VLM_NO_FFN=1` or remove the production
manifest and restart the camera manually.

## Lifetime and validation

Each report owns a fresh BPU worker shared by image encoding and the selected
language FFNs. Encoding uses the same original-image normalization and embedding
writer as the stable path. Keeping both stages in the same worker avoids an
extra native runtime teardown between them. Its model handles stay alive
for that report; the worker is terminated once all selected layers have
returned. Native teardown overlaps Chinese background writing and PDF layout.
The next report joins the previous worker before starting another encoder.
The language server itself stays warm. Recycling many native model contexts
inside a single Python process failed repeat-call tests and is not used.

Communication is a private Unix socket in a temporary directory. Shapes,
finite values, sequence of executed layers and artifact hashes are checked.
Only numerical timing/count statistics belong in public test reports. Camera
images, PDFs, captions, embeddings, their fingerprints and runtime logs remain
local. Complete report/PDF time matters more than individual BPU operator time;
model loading and driver release can erase operator-level gains.

## Measured candidate, 2026-10-24

See [numerical results](benchmarks/language-ffn-20261024.json). Twelve identical
saved originals were run with CPU language control before and after the
candidate. Both controls and the candidate used the same BPU visual encoder,
originals, 256 visual tokens, generative prompts, writer and A5 PDF renderer.
Priming samples are excluded; these are warm, paused-preview measurements.

| Path | Mean original to PDF | Range |
|---|---:|---:|
| CPU language, before | 7.088 s | 6.679–7.382 s |
| Shared encoder + FFNs 9–26 on BPU | 6.328 s | 6.022–6.702 s |
| CPU language, after | 7.146 s | 6.742–7.411 s |

The pooled CPU control is 7.117 s: the candidate saves **0.789 s (11.1%)**.
All twelve reports completed with eighteen verified FFN calls each. Encoder
outputs matched the controls exactly. Eight raw observations matched exactly;
four changed wording or omitted detail. Equality is a regression diagnostic,
not a recognition accuracy score. Existing recognition errors remain possible;
this small set does not establish a universal accuracy percentage.

The full 27-layer and early 9-layer variants were rejected as the default:
operator-level speedups did not consistently offset lifecycle overhead, and
some outputs changed an object subtype. Recycling native contexts also failed
repeat-call tests. The shared-worker candidate remains opt-in, with the
production manifest absent, pending a separately reviewed live integration.

A second [current-camera scene test](benchmarks/language-ffn-current-scene-20261024.json)
included first-use artifact verification and native loading. The candidate
needed **13.429 s cold and 6.544 s warm**, versus CPU controls of
10.754/7.129 s before and 10.269/7.249 s after. Both candidate observations
and encoder outputs matched their controls. First-use hash verification makes
this candidate slower from a completely cold start; the warm gain must not be
presented as a cold-start improvement. Existing app startup warmup can move
verification off the shutter path, but this still requires a live integration
check. The unchanged production app separately measured 12.420/11.816 s from
photo save to PDF in two real camera captures; these include active-app
scheduling costs and should not be substituted for paused-preview timings.
