# Reuse the TROS helper environment

Repeated photo reports previously sourced the TROS setup script for every
vision helper. The app now caches a successful environment overlay in memory
and starts subsequent helpers directly. Current process variables are merged
on each call. Environment contents are never logged or persisted.

The first capture is bounded by the remaining report deadline and three
seconds. Invalid or failed environment capture retains the original shell
launch; failures are not cached. The deadline is checked again before starting
the helper. Model weights, prompts, image source and output text are unchanged.

On the S100, a six-call comparison used the same saved camera original,
prewarmed writer and PDF fonts. No pages were printed. The live camera was
paused during measurement and resumed in `finally`.

| Call | Report plus PDF, seconds |
| --- | ---: |
| Baseline A | 7.230 |
| Candidate, first environment capture | 7.235 |
| Candidate, cached A | 6.698 |
| Baseline B | 7.219 |
| Baseline C | 7.250 |
| Candidate, cached B | 6.864 |

All six observations and final reports were exactly equal. Cached calls
averaged 6.781 seconds against 7.233 for baseline calls, about 0.45 seconds
less. The first call showed no material change in this small trial. These
figures exclude countdown and physical printer time and are not a general
latency guarantee. An earlier trial had substantial CPU vision timing drift;
its total-time results were not used to claim a gain.

The full 73-test suite passed, including success-only caching, current-variable
merging, invalid environment fallback, retry after failure, deadline accounting,
direct launch with the original photo and existing process cleanup tests.
