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
