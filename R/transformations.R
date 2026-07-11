# Transformation attacks (core spec v0.1, spec/transformations/transformations.md).
# Each returns a test-result object via build_test_result().

variant_row <- function(label, fit) {
  data.frame(label = label, estimate = fit$value, se = fit$se,
             ci_low = fit$ci_low, ci_high = fit$ci_high, n = fit$n,
             stringsAsFactors = FALSE)
}

collect_variants <- function(rows) {
  if (length(rows) == 0)
    return(data.frame(label = character(), estimate = numeric(), se = numeric(),
                      ci_low = numeric(), ci_high = numeric(), n = integer(),
                      stringsAsFactors = FALSE))
  do.call(rbind, rows)
}

test_unit_permutation <- function(audit, n_perm = 5) {
  cluster <- audit$structure$cluster
  invariance <- if (is.null(cluster)) "unit_permutation" else "unit_permutation_within_cluster"
  d <- audit$data
  rows <- list(); n_failed <- 0
  for (i in seq_len(n_perm)) {
    idx <- if (is.null(cluster)) sample.int(nrow(d)) else
      unlist(lapply(split(seq_len(nrow(d)), d[[cluster]]), sample), use.names = FALSE)
    fit <- fit_estimate(audit, d[idx, , drop = FALSE])
    if (is.null(fit)) n_failed <- n_failed + 1
    else rows[[length(rows) + 1]] <- variant_row(paste0("permutation ", i), fit)
  }
  build_test_result(audit, "unit_permutation", invariance, collect_variants(rows),
                    n_failed, deterministic = TRUE)
}

test_cluster_holdout <- function(audit) {
  cluster <- audit$structure$cluster
  if (is.null(cluster)) stop("cluster_holdout needs a declared cluster variable")
  d <- audit$data
  rows <- list(); n_failed <- 0
  for (cl in sort(unique(as.character(d[[cluster]])))) {
    fit <- fit_estimate(audit, d[as.character(d[[cluster]]) != cl, , drop = FALSE])
    if (is.null(fit)) n_failed <- n_failed + 1
    else rows[[length(rows) + 1]] <- variant_row(paste0("without ", cluster, " = ", cl), fit)
  }
  build_test_result(audit, "cluster_holdout", "cluster_exchangeability",
                    collect_variants(rows), n_failed)
}

test_temporal_split <- function(audit) {
  timevar <- audit$structure$time
  if (is.null(timevar)) stop("temporal_split needs a declared time variable")
  d <- audit$data
  tv <- d[[timevar]]
  vals <- sort(unique(tv))
  if (length(vals) < 2) stop("temporal_split needs at least two distinct time values")
  if (length(vals) <= 3) {
    groups <- lapply(vals, function(v) list(label = paste0(timevar, " = ", v), keep = tv == v))
  } else {
    med <- stats::median(tv)
    early <- tv <= med
    if (sum(early) < 10 || sum(!early) < 10) {  # degenerate median; split by rank halves
      early <- rank(tv, ties.method = "first") <= nrow(d) / 2
    }
    groups <- list(
      list(label = paste0(timevar, " early (", min(tv), "-", max(tv[early]), ")"), keep = early),
      list(label = paste0(timevar, " late (", min(tv[!early]), "-", max(tv), ")"), keep = !early))
  }
  rows <- list(); n_failed <- 0
  for (g in groups) {
    fit <- fit_estimate(audit, d[g$keep, , drop = FALSE])
    if (is.null(fit)) n_failed <- n_failed + 1
    else rows[[length(rows) + 1]] <- variant_row(g$label, fit)
  }
  build_test_result(audit, "temporal_split", "temporal_translation",
                    collect_variants(rows), n_failed)
}

test_subgroup_stability <- function(audit) {
  vars <- audit$structure$subgroups
  if (length(vars) == 0) stop("subgroup_stability needs declared subgroup variables")
  d <- audit$data
  rows <- list(); n_failed <- 0
  for (v in vars) {
    for (lev in sort(unique(as.character(d[[v]])))) {
      keep <- as.character(d[[v]]) == lev
      sub_audit <- audit
      # a subgroup variable cannot also adjust within its own stratum
      sub_audit$analysis$covariates <- setdiff(audit$analysis$covariates, v)
      fit <- fit_estimate(sub_audit, d[keep, , drop = FALSE])
      if (is.null(fit)) n_failed <- n_failed + 1
      else rows[[length(rows) + 1]] <- variant_row(paste0(v, " = ", lev), fit)
    }
  }
  build_test_result(audit, "subgroup_stability", "subgroup_transport",
                    collect_variants(rows), n_failed)
}

#' Run attacks against the declared invariances
#'
#' @param audit a structural_audit object with a populated ledger.
#' @param tests character vector from: unit_permutation, cluster_holdout,
#'   temporal_split, subgroup_stability, confounding_sensitivity.
#' @param seed integer seed for the permutation test, recorded implicitly in
#'   the audit through the variant estimates.
#' @param confounding_benchmark plausible unmeasured-confounding strength on the
#'   E-value (risk-ratio) scale, used by confounding_sensitivity (default 1.25).
test_invariance <- function(audit,
                            tests = c("unit_permutation", "cluster_holdout",
                                      "temporal_split", "subgroup_stability"),
                            seed = 1, confounding_benchmark = 1.25, outcome_node = NULL,
                            spatial_k = 3, tip_ratio = NULL, confounder_prevalence = 0.2) {
  stopifnot(inherits(audit, "structural_audit"))
  set.seed(seed)
  known <- c("unit_permutation", "cluster_holdout", "temporal_split",
             "subgroup_stability", "confounding_sensitivity", "graph_check",
             "adjustment_check", "spatial_holdout", "interference_check",
             "positivity_check", "confounding_scenarios")
  bad <- setdiff(tests, known)
  if (length(bad) > 0) stop("unknown tests: ", paste(bad, collapse = ", "))
  target_invariance <- function(t) switch(t,
    unit_permutation        = if (is.null(audit$structure$cluster)) "unit_permutation"
                              else "unit_permutation_within_cluster",
    cluster_holdout         = "cluster_exchangeability",
    temporal_split          = "temporal_translation",
    subgroup_stability      = "subgroup_transport",
    confounding_sensitivity = "unobserved_confounding",
    graph_check             = "causal_graph",
    adjustment_check        = "adjustment_sufficiency",
    spatial_holdout         = "spatial_translation",
    interference_check      = "network_relabelling",
    positivity_check        = "positivity",
    confounding_scenarios   = "unobserved_confounding")
  for (t in tests) {
    inv <- target_invariance(t)
    if (identical(ledger_status(audit, inv), "rejected")) {
      warning("skipping ", t, ": ", inv,
              " is rejected in the ledger and is not tested against (core spec, abstention rules)")
      next
    }
    res <- switch(t,
      unit_permutation        = test_unit_permutation(audit),
      cluster_holdout         = test_cluster_holdout(audit),
      temporal_split          = test_temporal_split(audit),
      subgroup_stability      = test_subgroup_stability(audit),
      confounding_sensitivity = test_confounding_sensitivity(audit, confounding_benchmark),
      graph_check             = test_graph_check(audit),
      adjustment_check        = test_adjustment_check(audit, outcome_node),
      spatial_holdout         = test_spatial_holdout(audit, spatial_k),
      interference_check      = test_interference(audit),
      positivity_check        = test_positivity(audit),
      confounding_scenarios   = test_confounding_scenarios(audit, confounder_prevalence, tip_ratio))
    audit$tests[[t]] <- res
    audit <- mark_tested(audit, res$invariance, res$verdict)
  }
  audit
}
