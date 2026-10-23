# Deterministic image observations on S100

The SmolVLM2-500M image and language weights stay unchanged. An optional
isolated build of the official TROS VLM node uses greedy decoding with seed 0
and six CPU decoder threads. The vision encoder still uses the BPU. Chinese
report writing remains on CPU, with conservative garment validation.

Prepare the optional node on S100:

```sh
python3 scripts/setup_report_decoder.py --root /home/sunrise/anime-camera
```

The builder downloads pinned official source archives to board storage,
builds with two low-priority jobs, and installs only under
`local-vlm/report-runtime`. It does not replace system binaries or libraries.
The helper verifies the binary hash and manifest before selection and uses
the original installed llama/ggml libraries. Missing or invalid optional
assets select the original official node. Rename `manifest.json` to disable
the optional decoder; no system package changes are necessary.

Seven privately reviewed photographs of the same jacket yielded the correct
outer garment in all seven greedy observations. The sampled baseline named
the jacket in five, abstained in one, and named a shirt in one. This small,
related photo set does not establish general accuracy. Colors and unseen
details remain excluded from the Chinese writer input. A face-only edge crop
is rejected before vision inference.

After priming the writer prompt cache and PDF fonts, a two-photo ABBA test
measured 7.485/7.573 seconds with the official decoder and 7.227/7.274 seconds
with the optional decoder, from saved original to printable PDF. Both
candidate reports passed garment validation. These times exclude camera
countdown, cold process loading and physical printing. An earlier health-only
warmup left the prompt cache cold and is not used as a speedup claim.

The reporter can also prefill the fixed Chinese system prompt while vision is
running, but only when the local server confirms an empty, idle prompt cache
and a reliable upper body is visible. Cached, busy or unknown slot states do
not trigger prefill. The background task is joined before completion, early
return or vision failure. No image is sent with this one-token prefill request.

In a repeated two-photo cold/warm comparison, cold saved-original-to-PDF time
fell from 11.818/11.326 seconds to 9.094/9.150 seconds. Warm requests showed no
regression in these samples. Unconditional prefill was rejected because it
made warm requests slower. A confirmed no-subject probe returns neutral copy
without starting either model, reducing that report stage from about 1.06 to
0.11–0.16 seconds. These are small local measurements, not latency guarantees.
