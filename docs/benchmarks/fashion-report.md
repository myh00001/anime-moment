# Faster and more accurate garment-grounded reports

The report option now supports a dedicated local garment classifier followed by
the existing Chinese report templates. YOLOX locates the largest visible person
in the same original camera photo; quantized Marqo-FashionSigLIP classifies its
pixels against 11 fixed categories. The anime photo is still used for the PDF.
No cloud image upload or second language-writing model is involved.

The classifier runs on CPU through the existing ARM ONNX Runtime. The live anime
models and their BPU path are unchanged. Capture freeze, waiting animation, PDF,
printing and the AI-report toggle keep their existing behavior. Old BPU reporting
remains available if the separately installed validated classifier assets are absent.

## Validation on S100, 2026-10-24

Acceptance target: at least 75% exact category matches including abstentions in
the denominator; capture-complete to printable PDF under 10 seconds.

- Development set: 48/63 matches (**76.2%**), across shirt/blouse, casual tops,
  sweater, cardigan, jacket, coat, hoodie, vest, dress, jumpsuit and cape examples.
- Disjoint holdout selected and labeled before inference: 28/34 (**82.4%**).
  This is a small public Fashionpedia validation sample, not a universal guarantee.
- Holdout selection seed 750010; excludes all 63 development source image IDs.
  The target is the largest human-annotated upper garment occupying >10% of the
  original image. All remaining qualifying images were eligible; the earlier
  development selection exhausted several rare classes, so this holdout has only
  the six groups below. Unsupported/uncertain predictions are not counted correct.

| Holdout group | Match / N |
|---|---:|
| Shirt/blouse | 6/6 |
| Top/T-shirt/sweatshirt | 4/6 |
| Jacket | 5/6 |
| Coat | 5/6 |
| Dress | 6/6 |
| Jumpsuit | 2/4 |

The combined 97 public images give 76/97 matches (78.4%), but this combined figure
includes development data and is **not** an independent validation score.
The candidate was frozen before the holdout and was not tuned on its errors.
See `fashion-report-validation.json` for source IDs, expected and emitted labels,
counts, individual timings and asset hashes. No pictures or raw user captions
are included in the repository.

Nine report+PDF calls: **1.019–2.231 seconds**, including first-use model loading
and PDF font work. First call: 2.231 seconds; subsequent calls: 1.019–1.195 seconds.
These calls include two saved camera originals, six public garment samples and
one empty image; they measure latency, not an additional independent accuracy set.
The real camera PDF-only integration test completed in **6.673 seconds including
the 3-second countdown**, using `original.jpg` for recognition. The scene had no
visible person and correctly produced neutral text. Positive-person coverage was
tested with saved originals. No extra test pages were printed.

## Limits and rejected candidates

- Layered garments remain difficult. The two saved camera jacket pictures were
  classified as the visible inner hoodie rather than the outer jacket. This is a
  main-garment mismatch, even though that inner garment exists. A strict initial
  jacket-only regression assertion failed. It was not counted as a correct jacket
  classification; later PDF smoke tests checked only the manually confirmed
  visible garment and absence of a fabricated dress. Do not conceal this failure.
- Jumpsuits, sleeveless tops and garment taxonomy boundaries still produce errors.
  A very short/occluded body can look like a different garment. No claim of 75%
  minimum on every category, every distance or real school-camera distribution.
- Clothing classification does not validate arbitrary objects, activities, people
  count, colors, printed text or identity. Those claims remain excluded from copy.
- Similarity scores are not calibrated confidence probabilities. An undetected
  person produces neutral text. Multi-person images describe the largest person.
- Short forced-choice SmolVLM and InternVL prompts showed strong answer biases
  and were rejected. Initial FashionCLIP gave 39/63; it was rejected in favor of
  FashionSigLIP. The latter alone and with person location each gave 48/63.

## Reproducing assets

Model sources: [Marqo-FashionSigLIP](https://huggingface.co/Marqo/marqo-fashionSigLIP)
and [OpenCV Zoo YOLOX](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_yolox).
Both are separately distributed; retain their upstream license notices.
Never commit weights, photos or generated PDFs.

On a development machine with NumPy, ONNX Runtime and tokenizers, use a directory
with sufficient space (on Windows prefer D:):

```text
python scripts/prepare_report_categories.py --output D:/s100-report-assets
```

Downloads are SHA-256 checked. The text encoder creates the fixed category vectors
once; it is not needed during capture. After validating the prepared artifacts,
activate the manifest with the script's `--activate` option. Copy only
`person.onnx`, `vision.onnx`, `categories.npz` and `manifest.json` to the board's
`local-vlm/report-category/`. The existing `local-vlm/gesture-ort/runtime` supplies
ARM ONNX Runtime. The service verifies all three artifact hashes at first use.

To revert the report path, restore the backed-up `local_report.py`; live anime
model files and all user settings require no change.
