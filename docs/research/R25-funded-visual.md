# R25 — Funded visual verification follow-up

Date2026-11-15. Status: development comparison/audit complete; selection/heldout pending.
Owner: inline. Decision: select a safer visual route without worsening other model responsibilities.

The user raised the cumulative OpenRouter ceiling to$5 TOTAL; key metadata verified limit5 and
usage1.970609815 at the new pass start. Per-run guards/settlement headroom remain. No new account,
purchase, private upload or hardware capture. Historical R22 runs retain their original limits.

## Same frozen category/count conditions

R22's40 licensed public photos/80 cases and source-separated48dev/32hold conditions are unchanged.
Actual CloudVerifier uses prompt7 and768px image transport. The completed Flash development run
is a preserved47-case prefix stopped at its$0.25 allowance plus an explicit one-case continuation,
with identical manifest/query/source/model identity checks. Original artifact remains failed;
the completed artifact links its hash and reuses all47 original outputs, not a silent rerun.
Continuation cost is separate. An input/model/label mismatch is rejected by regression tests.

Development: Lite41/48 correct proxy outcomes,6 proxy-unsafe positives; Flash46/48 and2 unsafe.
Median per-image elapsed2145.5ms Lite versus3280.5ms Flash on these runs. No category/count query
regressed in the paired proxy score. These are not spatial/instance/household accuracy labels.

Manual audit checked the newly detected remote in image232088 against the original annotation
bbox[446.6,270.31,28.78,10.88] and enlarged source detail: the small remote is indeed on the window
sill near the orange frame. The larger dark item on the sofa must not be assumed the target.
This confirms that particular location; it does not score all free-form location wording.

## Isolated confirmation on preserved positives

Rather than rerunning the primary and confounding its variation, apply the existing optional
category/location confirmation only to the17 cached Flash-positive judgments. All other outputs
stay untouched. This completed48/48 with46 correct proxy outcomes and1 unsafe: one unsafe
remote-like object was rejected, and one proxy-positive was also withheld.

The withheld proxy-positive (image76416) is a device depicted in a bus advertisement; the second
model identifies it as an iPod rather than a physical mobile phone. That proxy loss may be the
right product behavior. Class annotations do not distinguish every depiction or fine category;
never turn this46/48 into final physical-belonging accuracy. New depiction-condition diagnostics
and heldout verification will precede selection. A global vision-model swap could also slow
departure checks, so explicit object verification must be evaluated as its own responsibility.

Artifacts: data/runs/visual-funded-flash-development (47 complete), *-development-complete,
visual-funded-confirmation-development. Initial Flash reported responsecost$0.2341335; its
last-case continuation and confirmation costs live in their own artifacts. After confirmation,
observed key usage2.236859815/5; settlement may lag. No parallel paid benchmark ran in this phase.
