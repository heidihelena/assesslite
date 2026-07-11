# Positivity attack (AssessLite core spec v0.3, spec/positivity.md).
# Positivity: every unit could plausibly have either exposure level given its
# covariates. This fits a propensity score P(exposure = 1 | covariates), trims units
# whose propensity is near 0 or 1 (weak overlap) at increasing thresholds, and refits
# the outcome model. If the estimate leans on poorly-overlapping units, trimming moves
# it -- the finding depends on regions where positivity is strained.

test_positivity <- function(audit, alphas = c(0.01, 0.02, 0.05, 0.10)) {
  a <- audit$analysis
  d <- audit$data
  x <- d[[a$exposure]]
  if (!(is.numeric(x) && all(x %in% c(0, 1, NA))))
    stop("positivity_check needs a binary 0/1 exposure")
  if (length(a$covariates) == 0)
    stop("positivity_check needs covariates (overlap is defined in covariate space)")

  ps <- tryCatch(suppressWarnings(
    stats::fitted(stats::glm(stats::reformulate(a$covariates, a$exposure),
                             data = d, family = stats::binomial()))),
    error = function(e) NULL)
  if (is.null(ps))
    return(build_test_result(audit, "positivity_check", "positivity",
      data.frame(label = character(), estimate = numeric(), se = numeric(),
                 ci_low = numeric(), ci_high = numeric(), n = integer()), 0))

  # ps is over complete cases of the propensity model; align to rows
  ps_full <- rep(NA_real_, nrow(d)); ps_full[as.integer(names(ps))] <- ps
  rows <- list(); n_failed <- 0
  for (al in alphas) {
    keep <- !is.na(ps_full) & ps_full >= al & ps_full <= 1 - al
    trimmed <- sum(!is.na(ps_full)) - sum(keep)
    fit <- fit_estimate(audit, d[keep, , drop = FALSE])
    if (is.null(fit)) { n_failed <- n_failed + 1; next }
    rows[[length(rows) + 1]] <- data.frame(
      label = sprintf("trim propensity outside [%.2f, %.2f] (%d units)", al, 1 - al, trimmed),
      estimate = fit$value, se = fit$se, ci_low = fit$ci_low, ci_high = fit$ci_high,
      n = fit$n, stringsAsFactors = FALSE)
  }
  variants <- if (length(rows)) do.call(rbind, rows) else
    data.frame(label = character(), estimate = numeric(), se = numeric(),
               ci_low = numeric(), ci_high = numeric(), n = integer(), stringsAsFactors = FALSE)
  res <- build_test_result(audit, "positivity_check", "positivity", variants, n_failed)

  # overlap diagnostic: fraction of units in the weak-overlap region. A resolved
  # trimming shift is unstable; otherwise substantial weak overlap (>= 10%) makes the
  # positivity assumption not resolvable (strained but its effect on the conclusion
  # cannot be resolved by trimming); good overlap with no shift is stable.
  n_ps <- sum(!is.na(ps_full))
  n_extreme <- sum(!is.na(ps_full) & (ps_full < 0.05 | ps_full > 0.95))
  frac <- if (n_ps > 0) n_extreme / n_ps else NA_real_
  res$overlap <- list(frac_extreme = frac, n_extreme = n_extreme, n = n_ps)
  if (res$verdict != "unstable" && is.finite(frac) && frac >= 0.10) {
    res$verdict <- "not_resolvable"
    res$reading <- sprintf(paste0("%.1f%% of units have propensity below 0.05 or above 0.95 (the ",
      "weak-overlap region): positivity is strained -- many units have a near-deterministic exposure, ",
      "so the pooled estimate extrapolates. Trimming those units did not resolve a shift, so whether ",
      "the conclusion depends on them is not resolvable at this n"), 100 * frac)
  } else {
    res$reading <- paste0(res$reading, sprintf(
      " (%.1f%% of units are in the weak-overlap region, propensity < 0.05 or > 0.95)", 100 * frac))
  }
  res
}
