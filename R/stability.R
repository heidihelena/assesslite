# Stability metrics and the three-way verdict rule (core spec v0.1,
# spec/stability/metrics.md). Verdicts are deterministic given the metrics,
# so any audit file can be re-read back to its verdicts.

stability_metrics <- function(est0, se0, ci0_low, ci0_high, variants) {
  # se of the difference: var(est_j - est_0) ~ se_j^2 - se_0^2 for a variant that
  # the pooled estimate contains (see spec/stability/metrics.md)
  se_diff <- ifelse(!is.na(variants$se) & variants$se > se0,
                    sqrt(variants$se^2 - se0^2), se0)
  shift_z <- abs(variants$estimate - est0) / se_diff
  # two-sided p per variant, Bonferroni-adjusted for the number of variants so that
  # many blocks/clusters do not inflate the false-positive rate (a max-shift threshold
  # with m variants flags ~m x too often under stability)
  m_var <- nrow(variants)
  p_j <- 2 * stats::pnorm(-shift_z)
  shift_p_bonf <- if (m_var > 0) min(1, m_var * min(p_j, na.rm = TRUE)) else NA_real_
  flip <- sign(variants$estimate) != sign(est0) & sign(est0) != 0
  excl_null <- !is.na(variants$ci_low) & (variants$ci_low > 0 | variants$ci_high < 0)
  full_excl_null <- (ci0_low > 0 | ci0_high < 0)
  list(
    max_shift_z = max(shift_z, na.rm = TRUE),
    shift_p_bonf = shift_p_bonf,
    sign_flips_resolved = sum(flip & excl_null, na.rm = TRUE),
    sign_flips_unresolved = sum(flip & !excl_null, na.rm = TRUE),
    mds = 1.96 * stats::median(variants$se, na.rm = TRUE),
    null_crossings = sum(if (full_excl_null) !excl_null else excl_null, na.rm = TRUE)
  )
}

verdict_from_metrics <- function(m, est0, se0) {
  if (m$sign_flips_resolved >= 1 || (is.finite(m$shift_p_bonf) && m$shift_p_bonf < 0.05))
    return("unstable")
  if (is.finite(m$mds) && m$mds > max(2 * se0, abs(est0))) return("not_resolvable")
  "stable"
}

# Assemble one test-result object from a set of refits.
build_test_result <- function(audit, test, invariance, variants, n_failed = 0,
                              deterministic = FALSE) {
  e <- audit$estimate
  if (nrow(variants) == 0) {
    return(list(test = test, invariance = invariance, verdict = "not_resolvable",
                metrics = list(max_shift_z = NULL, sign_flips_resolved = 0L,
                               sign_flips_unresolved = 0L, mds = NULL,
                               null_crossings = 0L),
                variants = variants, n_failed = n_failed,
                reading = paste0("no variant model could be fitted; the attack on ",
                                 invariance, " is not resolvable with this data")))
  }
  if (deterministic) {
    tol <- 1e-8
    max_dev <- max(abs(variants$estimate - e$value))
    verdict <- if (max_dev > tol) "unstable" else "stable"
    reading <- if (verdict == "stable")
      "estimates are identical under permutation, as they must be; the estimator treats unit order symmetrically"
    else
      sprintf("estimates moved by up to %.2e under permutation of unit order; this points to an implementation or data problem, not a scientific finding", max_dev)
    metrics <- list(max_shift_z = max_dev / e$se, sign_flips_resolved = 0L,
                    sign_flips_unresolved = 0L, mds = NULL, null_crossings = 0L)
    return(list(test = test, invariance = invariance, verdict = verdict,
                metrics = metrics, variants = variants, n_failed = n_failed,
                reading = reading))
  }
  m <- stability_metrics(e$value, e$se, e$ci_low, e$ci_high, variants)
  verdict <- verdict_from_metrics(m, e$value, e$se)
  reading <- switch(verdict,
    stable = sprintf(
      "the largest variant shift was %.1f standard errors of the difference, within sampling noise, and no resolved sign change occurred; the attack could have detected a shift of about %.2f, so the claim of %s holds up under this test",
      m$max_shift_z, m$mds, gsub("_", " ", invariance)),
    unstable = sprintf(
      "the estimate moved by up to %.1f standard errors of the difference%s; %s does not hold up under this attack, and the pooling or transport it licenses loses its basis",
      m$max_shift_z,
      if (m$sign_flips_resolved > 0)
        sprintf(" and %d variant(s) showed a resolved sign change", m$sign_flips_resolved) else "",
      gsub("_", " ", invariance)),
    not_resolvable = sprintf(
      "variant intervals are too wide to distinguish stability from instability: the smallest detectable shift (about %.2f) exceeds both the estimate (%.2f) and twice its standard error; this attack is not resolvable at this n",
      m$mds, abs(e$value)))
  list(test = test, invariance = invariance, verdict = verdict,
       metrics = m, variants = variants, n_failed = n_failed, reading = reading)
}
