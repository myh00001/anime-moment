# Direct Chinese VLM trial and template reporting

The requested order was direct Chinese vision reporting first, then the
existing visual model with templates if the first option did not pass.

## Direct Chinese trial: not retained

The existing official S100 InternVL3-1B encoder and language assets were tested
with the same original-derived upper-body views and deterministic decoder.
A Chinese report prompt produced an unsupported description of multiple
students in white uniforms on both saved jacket photographs. Report-plus-PDF
times were 9.906 and 6.666 seconds, against 6.696 and 6.625 for the existing
pipeline. A shorter prompt removed activity context but abstained on both
clear jackets (5.535 and 5.636 seconds). This tested model/prompt combination
did not meet the accuracy requirement and was not deployed. This does not
establish that every Chinese VLM would fail.

## Retained option: existing vision plus templates

The production photo path now keeps the same SmolVLM2-500M BPU encoder,
deterministic language decoder, original-image subject localization and
conservative clothing-category extraction. It maps the supported observed
category to Chinese and selects one of three stable per-capture report
templates. Unknown or uncertain observations receive neutral copy. No text
server, text-generation request or Chinese prompt prefill is needed on this
BPU reporting path. The visual model still runs; this is not a filter-only
or image-independent report.

The previous two-model `LocalReporter` remains available through its explicit
API for comparison; normal `make_report` selects template mode. The AI report
toggle and photo/PDF/printing workflow retain their existing behavior.
Warm-up now prepares only the helper environment. No system package or anime
model was changed.

## Timing and accuracy checks

Two initial runs were discarded after another task restarted the camera
during measurement. The final serial comparison checked the camera instance
after each call and paused/resumed it in `finally`. No pages were printed.
All measured observations identified the same jacket category.

| State / call | Previous report + PDF (s) | Template report + PDF (s) |
| --- | ---: | ---: |
| Warm A | 7.091 | 6.220 |
| Warm B | 6.721 | 6.469 |
| Chinese writer stopped | 9.387 | 6.568 |

Warm means were 6.906 versus 6.345 seconds, about 8.1% less. The one
writer-stopped pair was about 30% less; it is a small compatibility/timing
sample, not a general speed guarantee. These figures exclude the three-second
countdown and physical printer time. Visual observation remains the dominant
cost. Template prose has less variation than unconstrained text generation.

The full 80-test suite passed. New tests cover all six supported category
translations, uncertain observations, stable template variants, original-photo
helper input, no text-model calls and the default production selection.
Private photographs, PDFs and raw report records are not included here.
