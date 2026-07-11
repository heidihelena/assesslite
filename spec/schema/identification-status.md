# Identification and decision status vocabulary (core spec v0.1)

## Per-test verdicts (three-way, always)

Every transformation test returns exactly one of:

- `stable` — the conclusion survived this attack, and the test had enough precision that
  a material shift would have been seen.
- `unstable` — a resolved violation: a variant estimate moved materially or flipped sign,
  and the movement is distinguishable from sampling noise.
- `not_resolvable` — the test could not distinguish stable from unstable at this n.
  Variant intervals are too wide relative to the shift the test is trying to detect.

`not_resolvable` is not a soft pass. It means the attack was run and the data could not
answer it. Binary pass/fail verdicts are forbidden across all implementations: every
stability gate is a bright line on a noisy estimate, and the audit must say whether the
line was resolvable.

## Decision statuses

The decision layer returns exactly one of:

- `proceed` — every assumed invariance with an available attack was attacked and came
  back `stable`, and no abstention rule fired.
- `conditional` — no resolved instability, but at least one assumed invariance is
  `untested` or came back `not_resolvable`. The conclusion stands only conditional on
  the unattacked or unresolved claims, which the audit lists by name.
- `abstain` — a resolved instability on an invariance the analysis relies on, or a
  user-declared abstention rule fired (e.g. the estimate's sign changes under a
  plausible structural alternative, or a variant crosses a declared decision threshold).

An `abstain` is a result, not a failure of the tool. It records that under the declared
structural alternatives the conclusion does not hold still, and states which
transformation broke it.
