# Decision and abstention rules (core spec v0.1)

Inputs: the ledger (invariances with statuses), the set of test results (verdicts), and
optional user-declared abstention rules.

## Base rule (always applied)

1. `abstain` if any test on an `assumed` invariance returned `unstable`.
2. else `conditional` if any `assumed` invariance is `untested` or any test returned
   `not_resolvable`.
3. else `proceed`.

A `rejected` invariance is never tested against and never blocks a decision; its role is
to constrain the model specification and the claim's domain (recorded in the audit).

## User-declared abstention rules (optional, evaluated before the base rule can `proceed`)

- `estimate_sign_changes: true` — abstain if any variant point estimate under any run
  test has the opposite sign from the full-sample estimate AND its interval excludes 0.
- `effect_crosses_threshold: <t>` — abstain if the full-sample estimate and any variant
  fall on opposite sides of the declared decision threshold t (natural scale), AND the
  crossing is resolved (the variant's interval excludes t). If the crossing is present
  but unresolved (interval includes t), the decision is capped at `conditional`, never
  `proceed` — a threshold gate on an interval that straddles the line is not a fail,
  it is not resolvable.

## Output requirements

The decision object must name, explicitly:
- which invariances did the identification work (`assumed`, tested, `stable`),
- which are the exposed surface (`untested` or `not_resolvable`),
- which transformation broke the conclusion, when the status is `abstain`,
- the rationale sentence for the status, in plain language, suitable for a methods
  or limitations paragraph.
