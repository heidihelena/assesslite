# Confounding scenario array (AssessLite core spec v0.3, spec/scenarios.md).
# A deterministic bias-analysis array (Lin, Psaty & Kronmal 1998; VanderWeele & Arah
# 2011): for a grid of unmeasured-confounder scenarios, shift the estimate toward the
# null by the implied confounding bias and record where the conclusion tips past a
# target (the null, or a declared decision threshold). This is the estimator-failure
# map that complements the single-number E-value (confounding_sensitivity).

# bias factor for a binary confounder U with outcome risk-ratio rr_uy, prevalence p0 in
# the unexposed and p1 = p0 + delta in the exposed
bias_factor <- function(rr_uy, p0, delta) {
  p1 <- min(1, max(0, p0 + delta))
  (1 + (rr_uy - 1) * p1) / (1 + (rr_uy - 1) * p0)
}

test_confounding_scenarios <- function(audit, confounder_prevalence = 0.2, tip_ratio = NULL,
                                       rr_uy_grid = c(1.5, 2, 3, 4),
                                       delta_grid = c(0.1, 0.2, 0.3, 0.4),
                                       plausible_rr_uy = 2, plausible_delta = 0.2) {
  est <- audit$estimate
  estimator <- audit$analysis$estimator
  if (!estimator %in% c("coxph", "glm_binomial"))
    stop("confounding_scenarios (bias analysis) is defined for ratio-scale estimators only ",
         "(coxph, glm_binomial); not for '", estimator, "' on a ", audit$analysis$scale)

  obs <- est$value                                  # observed effect on the log-ratio scale
  s <- sign(obs)
  target <- if (is.null(tip_ratio)) 0 else log(tip_ratio)
  # not resolvable if the interval already includes the target
  includes_target <- est$ci_low <= target && est$ci_high >= target

  cells <- list(); min_tip <- NULL
  for (rr in rr_uy_grid) for (dl in delta_grid) {
    bf <- bias_factor(rr, confounder_prevalence, dl)
    adj <- obs - s * log(bf)                        # shift toward the null by the bias magnitude
    tipped <- if (s >= 0) adj < target else adj > target
    cells[[length(cells) + 1]] <- list(rr_uy = rr, delta = dl, bias_factor = round(bf, 3),
                                       adjusted_estimate = round(adj, 4), tips = tipped)
    if (tipped && (rr <= plausible_rr_uy && dl <= plausible_delta) &&
        (is.null(min_tip) || rr * dl < min_tip$rr_uy * min_tip$delta))
      min_tip <- list(rr_uy = rr, delta = dl)
  }

  plausible_tip <- any(vapply(cells, function(c)
    c$tips && c$rr_uy <= plausible_rr_uy && c$delta <= plausible_delta, logical(1)))
  verdict <- if (includes_target) "not_resolvable"
             else if (plausible_tip) "unstable" else "stable"

  measure <- if (estimator == "coxph") "hazard ratio" else "odds ratio"
  tgt_txt <- if (is.null(tip_ratio)) "no effect" else sprintf("a %s of %.2f", measure, tip_ratio)
  reading <- switch(verdict,
    not_resolvable = sprintf(paste0("the interval already includes %s on the ratio scale, so the ",
      "confounding needed to reach it is not defined; the effect itself is not established beyond ",
      "the target"), tgt_txt),
    unstable = sprintf(paste0("an unmeasured confounder within the plausible bound (outcome risk ratio ",
      "<= %.1f, exposure prevalence difference <= %.2f, at prevalence %.2f) would move the estimate ",
      "past %s -- the smallest such is risk ratio %.1f with prevalence difference %.2f; the conclusion ",
      "does not hold up against plausible confounding %s"),
      plausible_rr_uy, plausible_delta, confounder_prevalence, tgt_txt,
      min_tip$rr_uy, min_tip$delta,
      sprintf("(bias analysis on the risk-ratio scale under the rare-outcome approximation for the %s)", measure)),
    stable = sprintf(paste0("no unmeasured confounder within the plausible bound (outcome risk ratio ",
      "<= %.1f, prevalence difference <= %.2f) moves the estimate past %s; only stronger-than-plausible ",
      "confounding would tip the conclusion %s"),
      plausible_rr_uy, plausible_delta, tgt_txt,
      sprintf("(bias analysis on the risk-ratio scale under the rare-outcome approximation for the %s)", measure)))

  list(test = "confounding_scenarios", invariance = "unobserved_confounding", verdict = verdict,
       metrics = NULL,
       scenarios = list(target = if (is.null(tip_ratio)) NA_real_ else tip_ratio,
                        confounder_prevalence = confounder_prevalence,
                        plausible_rr_uy = plausible_rr_uy, plausible_delta = plausible_delta,
                        minimal_tipping = min_tip, cells = cells),
       variants = data.frame(label = character(), estimate = numeric(), se = numeric(),
                             ci_low = numeric(), ci_high = numeric(), n = integer(),
                             stringsAsFactors = FALSE),
       n_failed = 0L, reading = reading)
}
