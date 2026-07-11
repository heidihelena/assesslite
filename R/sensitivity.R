# Sensitivity attacks (AssessLite core spec v0.2, spec/stability/sensitivity.md).
# A sensitivity attack asks how strong an unobserved violation would have to be to
# overturn the conclusion. It produces no variant refits, but carries a three-way
# verdict in the same vocabulary as every transformation attack.

# E-value of a ratio (VanderWeele & Ding, 2017): the minimum strength of association,
# on the risk-ratio scale, that an unmeasured confounder would need with both exposure
# and outcome to explain the association away.
evalue_from_ratio <- function(r) {
  r <- ifelse(r < 1, 1 / r, r)
  r + sqrt(r * (r - 1))
}

# confounding_sensitivity: attacks the unobserved_confounding invariance with the E-value.
# Ratio-scale estimators only (coxph, glm_binomial). Not defined for a linear coefficient.
test_confounding_sensitivity <- function(audit, benchmark = 1.25) {
  est <- audit$estimate
  estimator <- audit$analysis$estimator
  if (!estimator %in% c("coxph", "glm_binomial"))
    stop("confounding_sensitivity (E-value) is defined for ratio-scale estimators only ",
         "(coxph, glm_binomial); not for '", estimator, "' on a ", audit$analysis$scale)

  rr <- exp(est$value); ll <- exp(est$ci_low); ul <- exp(est$ci_high)
  e_point <- evalue_from_ratio(rr)
  includes_null <- (ll <= 1 && ul >= 1)
  e_ci <- if (includes_null) 1 else if (rr > 1) evalue_from_ratio(ll) else evalue_from_ratio(ul)

  verdict <- if (includes_null) "not_resolvable" else if (e_ci <= benchmark) "unstable" else "stable"
  measure <- if (estimator == "coxph") "hazard ratio" else "odds ratio"
  caveat <- paste0("(E-value on the risk-ratio scale under the rare-outcome approximation for the ",
                   measure, ")")
  reading <- switch(verdict,
    not_resolvable = paste0(
      "the confidence interval already includes no effect on the ratio scale, so the unmeasured ",
      "confounding needed to explain the result away is not defined (E-value for the interval = 1); ",
      "this attack is not resolvable -- the effect itself is not established"),
    unstable = sprintf(paste0(
      "an unmeasured confounder associated with both exposure and outcome by a risk ratio of about ",
      "%.2f would move the interval to include no effect; that is no stronger than the declared ",
      "plausible confounding (%.2f), so no-unmeasured-confounding does not hold up %s"),
      e_ci, benchmark, caveat),
    stable = sprintf(paste0(
      "explaining the interval away would require unmeasured confounding of at least %.2f on the ",
      "risk-ratio scale, stronger than the declared plausible benchmark (%.2f); the conclusion is ",
      "robust to confounding at that benchmark (E-value for the point estimate %.2f) %s"),
      e_ci, benchmark, e_point, caveat))

  list(test = "confounding_sensitivity", invariance = "unobserved_confounding",
       verdict = verdict, metrics = NULL,
       sensitivity = list(e_value_point = e_point, e_value_ci = e_ci,
                          rr_point = rr, rr_ci_low = ll, rr_ci_high = ul,
                          benchmark = benchmark),
       variants = data.frame(label = character(), estimate = numeric(), se = numeric(),
                             ci_low = numeric(), ci_high = numeric(), n = integer(),
                             stringsAsFactors = FALSE),
       n_failed = 0L, reading = reading)
}
