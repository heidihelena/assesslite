# Report structure (core spec v0.1)

Every report, in every language, renders these sections in this order. The order is the
argument: the reader meets the assumptions before the estimate, and the estimate before
the verdicts — the audit trail runs from the scientific claim about invariance to the
identification result, not backwards from the final number.

1. **Header** — estimand, unit, data fingerprint, engine and spec versions, timestamp.
2. **Declared structure** — cluster, time, subgroup variables; the observational world
   as the analyst described it.
3. **Invariance ledger** — every assumed and rejected invariance with rationale and what
   it licenses. Rejected claims shown with what their rejection removed from scope.
4. **Full-sample estimate** — point, interval, n, scale. One row. Deliberately not the
   headline of the report.
5. **Attacks** — one block per test: which invariance it probes, variant table
   (label, estimate, interval, n), metrics, the three-way verdict, and a one-sentence
   reading in plain language.
6. **Decision** — status (proceed / conditional / abstain), the rationale sentence,
   load-bearing invariances, exposed surface (untested / not resolvable), and which
   transformation broke the conclusion if abstaining.
7. **Limitations text** — auto-drafted paragraph for a manuscript's methods/limitations
   section, listing the exposed surface by name. Marked as a draft for the analyst to
   edit, not to paste blindly.

Vocabulary rules for all rendered text: check / test / assess — never verify, prove,
guarantee, validate. Three-way verdicts rendered with `not_resolvable` shown as
"not resolvable at this n", never as a pass or a fail.
