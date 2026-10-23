# Do not turn uncertain clothing observations into facts

The category extractor previously matched garment words even in phrases such
as “Maybe a jacket”, “Not wearing a jacket” and “A jacket or sweater”. Those
mentions are insufficient evidence for a definite Chinese clothing claim.

The extractor now abstains on these uncertainty, negation and alternative
patterns. The existing neutral report handles the abstention, with no second
model call. Definite observations retain the existing category mapping.

Validation: the 74-test suite passed, including six constructed negative or
uncertain observations and a definite jacket observation. All six observations
from the preceding saved-original report comparison retained exactly the same
category result. This is a conservative text guard, not evidence of improved
visual model accuracy or a calibrated confidence score. Models, prompts,
resolution and photo source remain unchanged.
