---
title: 'AssessLite: structural assumption assessment for causal analysis in R and Python'
tags:
  - R
  - Python
  - causal inference
  - epidemiology
  - sensitivity analysis
  - assumptions
  - reproducibility
authors:
  - name: Heidi Helena Andersén
    orcid: 0000-0001-5923-5865
    affiliation: 1
affiliations:
  - name: Vahtian, Finland
    index: 1
date: 12 July 2026
bibliography: paper.bib
---

# Summary

Every causal estimate from observational data borrows strength across units, places, or
times. That borrowing is licensed by invariance assumptions — claims that certain
transformations of the observed system leave the causal mechanism unchanged — which usually
stay implicit inside exchangeability, i.i.d. sampling, or transportability. Weinstein and
Blei make this point explicit for dependent data: generalisation from a single structured
realisation requires a stated symmetry, and the substantive scientific question is *which*
invariances may legitimately be imposed [@weinstein2026geometric].

AssessLite is the auditing layer for that question. The analyst declares the structure of
the observational world (clusters, calendar time, subgroups, spatial coordinates, a contact
network, a causal graph with latent nodes) and records each invariance claim in a ledger,
with a rationale and the inferential step it licenses. The package then attacks the ledger:
transformation attacks (unit permutation, leave-one-cluster-out, temporal splits, subgroup
refits, spatial block holdout), sensitivity attacks (the E-value [@vanderweele2017evalue]
and a bias-analysis scenario array [@lin1998bias; @vanderweele2011bias]), structural checks
(testable implications of the declared graph, backdoor-criterion validity of the adjusted
covariate set with identifiability under latent confounding [@pearl2009causality;
@vanderzander2014adjustment], positivity/overlap trimming), residual spatial autocorrelation
[@moran1950; @cliff1981spatial], and network interference against SUTVA. Every attack
returns a three-way verdict — stable, unstable, or *not resolvable at this n* — and a
decision layer aggregates the ledger into proceed, conditional, or abstain. The complete
reasoning path is exported as a JSON audit record validated against a shared schema, plus a
self-contained HTML report ending in an auto-drafted limitations paragraph.

AssessLite is implemented twice, natively: an R package and a Python package that share one
language-neutral specification and emit schema-identical audit records. Both engines are
dependency-light by design (base R; numpy and pandas), with Cox proportional-hazards and
GLM estimators implemented in-package; the Python Cox implementation reproduces R's
`coxph(ties = "breslow")` coefficients and standard errors exactly, and deterministic
attacks agree across the two engines to machine precision.

# Statement of need

Applied researchers have good tools for individual pieces of this workflow: DAGitty derives
adjustment sets and testable implications from a causal diagram [@textor2016dagitty]; DoWhy
separates modelling, identification, estimation, and refutation [@sharma2020dowhy];
sensemakr and the E-value quantify robustness to unmeasured confounding
[@cinelli2020sensemakr; @vanderweele2017evalue]; invariant causal prediction uses
invariance across environments as a discovery criterion [@peters2016icp]. What these tools
do not provide is the connecting layer: an explicit, auditable map from the analyst's
declared scientific structure, through named invariance claims and what each one licenses,
to attacks on those claims and a decision that can abstain.

AssessLite occupies that layer. Three design choices distinguish it. First, assumptions are
first-class objects: every attack targets a named claim in a vocabulary fixed by the
specification, a claim cannot enter the ledger without a rationale and a licence, and when
several attacks target one claim the ledger keeps the worst verdict. Second, verdicts are
three-way: every stability gate is a bright line on a noisy estimate, so the package
reports whether the line was resolvable at the available sample size rather than forcing a
pass/fail; holdout-style attacks use a Bonferroni-adjusted shift test so that many clusters
or blocks do not inflate false alarms. Third, the audit is the output: the JSON record
contains every variant estimate, metric, threshold, and reading needed to re-derive each
verdict, making the assumption audit as archivable and reviewable as the analysis itself.

The package is aimed at epidemiologists, registry researchers, and biostatisticians whose
data strain the i.i.d. ideal — multicentre cohorts, long accrual windows, geographic
variation, and contact structure — and who need to state, attack, and report the
assumptions their conclusions depend on. It records claim-to-evidence support, never truth:
a stable verdict means a conclusion survived the attacks that were run, at the precision
the data allowed.

# Functionality

The R interface follows one loop: `structural_audit()` declares the data structure and fits
the estimator; `assume_invariance()`/`reject_invariance()` build the ledger;
`declare_graph()` (optionally with latent nodes) adds a causal diagram;
`test_invariance()` runs any of twelve attacks; `decide()` applies the abstention rules;
`write_audit()` and `render_report()` export the audit record and report;
`assumption_lattice()` refits the estimate under every pool-or-stratify combination of the
pooling axes and renders the resulting Hasse diagram. The Python interface exposes the same
objects through a `StructuralAudit` class with a fluent API. Notable capabilities include
identifiability analysis under latent confounding — including *identification repair*,
which names the latent measurement that would restore an identifiable effect — and residual
spatial autocorrelation using martingale residuals for survival outcomes.

Both engines carry test suites (about 130 tests combined) run in continuous integration
together with a full `R CMD check`; cross-language agreement is asserted on fixed datasets,
and audit records from both engines are validated against the shared JSON Schema. Releases
are published to PyPI and r-universe and archived on Zenodo
[@andersen2026assesslite].

# Limitations

AssessLite audits declared structure; it does not learn a graph, and a stable verdict does
not establish an assumption — Markov-equivalent graphs share testable implications, and
untestable claims are reported as the exposed surface rather than silently passed.
Conditional-independence checks use partial correlation (a linear approximation), ratio-scale
sensitivity analyses use the rare-outcome approximation, and the spatial attack diagnoses
residual autocorrelation rather than fitting a spatial-process mechanism model. These
boundaries are stated in the specification files and in the rendered readings.

# Acknowledgements

The assumptions-first framing was sparked by Weinstein and Blei's geometric causal models
[@weinstein2026geometric]. AssessLite was developed with the assistance of Claude (Anthropic)
under the author's direction; the author reviewed and is responsible for all design
decisions, code, and text.

# References
