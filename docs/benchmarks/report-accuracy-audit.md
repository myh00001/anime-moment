# Report accuracy audit — 2026-10-24

This is an end-to-end audit of the deployed SmolVLM2-500M caption, subject crop,
category filter and report template. It is not a general-purpose vision benchmark.
The model, prompt and category mapping were not changed during this audit.

## Protocol

- Public source: [Fashionpedia](https://github.com/cvdfoundation/fashionpedia),
  validation 2020 human instance annotations. Images remain outside this repository.
- 63 original images selected before inference, stratified across shirt/blouse,
  top/T-shirt/sweatshirt, sweater, jacket, coat, dress, jumpsuit, cape, cardigan,
  vest and hood-related examples. Selection seeds: 20261024 and 20261025.
- Official garment annotations define category targets. Hood-related targets were
  visually reviewed before inference. Supported mappings and case IDs were fixed
  in advance. A missing face remains an abstention; it is not excluded afterward.
- Nine additional derived cases test three subject sizes, blur, low light,
  90-degree rotation, an empty image, hidden face and a two-person montage.
  These reuse originals and are reported separately, not as independent samples.
  Image scaling is not a measurement of recognition at a physical distance.
- Production upper-body crop, largest-face selection, BPU encoder and greedy
  six-thread decoder were used. Captions used the same original-image path as
  production, never an anime rendering. No test pages were printed.
- Preview initially ran alongside the test, then was paused with user permission
  and resumed afterward. These mixed-load timings are not production speed data.

## Scoring and limits

`correct` means the emitted category matches the predefined target; `abstain`
means no specific category survived the production filter. Runtime errors stay
in the denominator. Precision among specific outputs and coverage are separate
from strict accuracy including abstentions.

Dress, jumpsuit, cape, cardigan and vest have no dedicated production output
category. Their neutral reports are coverage gaps, not correct classifications.
Specific outputs for those samples require visual review because layered garments
may contain a legitimate secondary category.

Fashionpedia's top/T-shirt/sweatshirt group is coarse. English “shirt” can describe
a casual top generically, jacket/hoodie boundaries can be ambiguous, and layered
clothes can cause the caption to describe an inner garment. Strict mismatches are
retained, rather than changing labels after seeing predictions. They must not all
be interpreted as unambiguous hallucinations.

This small fashion-image sample is not representative of a school camera feed.
It does not evaluate arbitrary objects, activities, text, colors or identity.
Production templates deliberately omit those claims. No broad accuracy guarantee
can be inferred from this test.

The sanitized case records and aggregate results accompany this document. They
contain labels and numeric results only, without images or raw captions.

## Results

All 72 cases completed without runtime errors. Preview was resumed and its fresh
heartbeat/output verified; no printing settings or model files were changed.

For 35 independent originals whose targets are supported, 16 matched, six
mismatched and 13 abstained. Strict accuracy including abstentions is **45.7%**;
precision among the 22 specific outputs is **72.7%**, with **62.9%** coverage.
These figures do not establish high general recognition accuracy.

| Target group | N | Match | Mismatch | Abstain |
|---|---:|---:|---:|---:|
| Shirt/blouse | 6 | 1 | 0 | 5 |
| Top/T-shirt/sweatshirt | 6 | 1 | 1 | 4 |
| Sweater | 5 | 3 | 0 | 2 |
| Jacket, including separate hooded jacket case | 7 | 4 | 2 | 1 |
| Coat | 6 | 4 | 2 | 0 |
| Hoodie | 4 | 3 | 1 | 0 |
| Ambiguous collared top | 1 | 0 | 0 | 1 |

Of 28 unsupported-category originals, 27 produced neutral reports; one cape
(F43) was called a jacket. Visual review confirms the cape/jacket mismatch.
Six supported-category mismatches are retained: F11, F20, F21, F25, F26, F60.
F11 uses generic English “shirt” for a casual top; F20 is layered clothing with
a shirt under a blazer; F21 sits near the jacket/zip-hoodie taxonomy boundary.
The score deliberately does not reclassify these after inference. F25/F26 show
the upper-body crop's weakness at distinguishing long coats from jackets; F60
is a hoodie misclassified as a jacket.

Separate robustness results: three subject sizes, blur, low light and the
two-person montage emitted the expected jacket category (six cases). Empty and
face-hidden images stayed neutral (two cases). The rotated image abstained.
These single examples do not prove robust performance under those conditions.

Two blouse examples (F03/F06) contained the correct garment word in the private
raw captions but were discarded because the production mapping recognizes
“shirt”, not “blouse”. This is a parser coverage defect, separate from vision
errors. No mapping was tuned on this test or deployed during the audit.

Next work should measure a stronger visual model and carefully scoped category
normalization on a separate holdout set, including school scenes, multiple
people, objects and actions. Template safety is not a substitute for visual
recognition accuracy. This audit covers clothing and a few scene guards only.
