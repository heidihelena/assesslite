# Contributing to AssessLite

Thank you for your interest. AssessLite is one specification with two native engines, and
contributions are expected to respect that shape.

## Reporting problems

Open an issue at https://github.com/heidihelena/assesslite/issues. For a suspected wrong
verdict, please attach the audit record (JSON) and, if possible, a minimal simulated dataset
that reproduces it — never real patient or registry data.

## Ground rules for changes

- **Spec first.** Anything that changes the meaning of an audit record — vocabulary,
  metrics, verdict rules, schema — is a change to `spec/` before it is a change to code,
  and both engines must implement it in the same pull request.
- **Both engines, always.** A feature that exists in only one language does not merge.
  Deterministic computations must agree across R and Python on fixed data (add a
  cross-language test).
- **Three-way verdicts.** Attacks return stable / unstable / not resolvable. Binary
  pass/fail verdicts, or language that promises truth (verify, prove, guarantee), will be
  asked to change.
- **No new hard dependencies.** The engines are deliberately base R and numpy/pandas.
- **Tests and checks.** `testthat` and `pytest` suites must pass, and `R CMD check` must be
  clean; CI runs both on every pull request.

## Seeking support

Questions about usage are welcome as GitHub issues. Please include the package version
(`packageVersion("assesslite")` or `assesslite.__version__`) and the relevant reading or
verdict text.
