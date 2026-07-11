# Constructor and estimator for a structural audit.
# Implements core spec v0.1 (see spec/ in the assesslite repository).

SPEC_VERSION <- "0.1"

#' Canonical invariance identifiers (core spec v0.1)
invariance_vocabulary <- function() {
  c("unit_permutation",
    "unit_permutation_within_cluster",
    "cluster_exchangeability",
    "temporal_translation",
    "subgroup_transport",
    "unobserved_confounding",
    "causal_graph",
    "adjustment_sufficiency",
    "spatial_translation",
    "network_relabelling")
}

#' Declare the structure of a causal analysis and open its audit
#'
#' @param data data frame of the analysis sample.
#' @param outcome a single column name for a GLM outcome, or c(time, status)
#'   column names for a Cox model (requires the survival package).
#' @param exposure column name of the exposure of interest.
#' @param covariates character vector of adjustment covariate names.
#' @param cluster column name of the cluster variable (hospital, site), or NULL.
#' @param time column name of the calendar-time variable, or NULL.
#' @param subgroups character vector of subgroup variable names.
#' @param unit what one row is (e.g. "patient").
#' @param estimand plain-language statement of the target quantity.
structural_audit <- function(data, outcome, exposure, covariates = character(),
                             cluster = NULL, time = NULL, subgroups = character(),
                             coords = NULL, unit_id = NULL, edges = NULL,
                             unit = "unit", estimand = NULL) {
  stopifnot(is.data.frame(data))
  if (!is.null(coords) && length(coords) != 2)
    stop("coords must be two column names, c(x, y) or c(lon, lat)")
  needed <- c(outcome, exposure, covariates, cluster, time, subgroups, coords, unit_id)
  missing_cols <- setdiff(needed, names(data))
  if (length(missing_cols) > 0)
    stop("columns not in data: ", paste(missing_cols, collapse = ", "))
  if (!is.null(coords) && !all(vapply(coords, function(c) is.numeric(data[[c]]), logical(1))))
    stop("coords columns must be numeric")
  network <- NULL
  if (!is.null(edges)) {
    if (is.null(unit_id)) stop("edges require a unit_id column naming each unit")
    if (!is.data.frame(edges) || ncol(edges) < 2)
      stop("edges must be a data frame of two columns of unit ids (undirected)")
    if (anyDuplicated(as.character(data[[unit_id]])))
      stop("unit_id values must be unique (one row per unit)")
    network <- list(unit_id = unit_id, edges = edges[, 1:2], n_edges = nrow(edges))
  }

  if (length(outcome) == 2) {
    if (!requireNamespace("survival", quietly = TRUE))
      stop("a two-column outcome (time, status) needs the survival package")
    estimator <- "coxph"
    scale <- "log hazard ratio"
  } else if (length(outcome) == 1) {
    y <- data[[outcome]]
    if (is.numeric(y) && all(y %in% c(0, 1, NA))) {
      estimator <- "glm_binomial"; scale <- "log odds ratio"
    } else if (is.numeric(y)) {
      estimator <- "glm_gaussian"; scale <- "linear coefficient"
    } else stop("outcome must be numeric (binary 0/1 or continuous), or c(time, status)")
  } else stop("outcome must be one column name or c(time, status)")

  if (is.null(estimand))
    estimand <- paste0("effect of ", exposure, " on ", paste(outcome, collapse = "/"),
                       " (", scale, ")")

  audit <- structure(list(
    data = data,
    analysis = list(unit = unit, outcome = paste(outcome, collapse = "/"),
                    outcome_cols = outcome, exposure = exposure,
                    covariates = covariates, estimand = estimand,
                    estimator = estimator, scale = scale),
    structure = list(cluster = cluster, time = time, subgroups = subgroups, coords = coords,
                     unit_id = unit_id,
                     n_edges = if (is.null(network)) NULL else network$n_edges),
    network = network,
    ledger = list(),
    tests = list(),
    estimate = NULL,
    decision = NULL
  ), class = "structural_audit")

  audit$estimate <- fit_estimate(audit, data)
  if (is.null(audit$estimate))
    stop("the full-sample model could not be fitted; audit not opened")
  audit
}

# Fit the declared estimator on a data subset; return the exposure coefficient
# on its natural scale, or NULL if the fit fails. `strata` names variables to
# condition on without pooling: Cox strata() (separate baseline hazards), or
# GLM fixed-effect factors. Used by the assumption lattice to refit under weaker
# pooling commitments.
fit_estimate <- function(audit, data, strata = character(), coef_of = NULL) {
  a <- audit$analysis
  term <- if (is.null(coef_of)) a$exposure else coef_of
  strata <- setdiff(strata, c(a$exposure, a$covariates))
  rhs <- paste(c(a$exposure, a$covariates), collapse = " + ")
  fit <- tryCatch(suppressWarnings({
    if (a$estimator == "coxph") {
      st <- if (length(strata) > 0)
        paste0(" + ", paste0("survival::strata(", strata, ")", collapse = " + ")) else ""
      f <- stats::as.formula(paste0("survival::Surv(", a$outcome_cols[1], ", ",
                                    a$outcome_cols[2], ") ~ ", rhs, st))
      survival::coxph(f, data = data)
    } else {
      st <- if (length(strata) > 0)
        paste0(" + ", paste0("factor(", strata, ")", collapse = " + ")) else ""
      f <- stats::as.formula(paste0(a$outcome_cols[1], " ~ ", rhs, st))
      fam <- if (a$estimator == "glm_binomial") stats::binomial() else stats::gaussian()
      stats::glm(f, data = data, family = fam)
    }
  }), error = function(e) NULL)
  if (is.null(fit)) return(NULL)

  cf <- stats::coef(fit)
  idx <- which(startsWith(names(cf), term))
  if (length(idx) == 0) return(NULL)
  idx <- idx[1]
  se <- sqrt(diag(stats::vcov(fit)))[idx]
  est <- unname(cf[idx])
  if (!is.finite(est) || !is.finite(se)) return(NULL)
  n <- if (a$estimator == "coxph") fit$n else stats::nobs(fit)
  list(value = est, se = unname(se),
       ci_low = est - 1.96 * unname(se), ci_high = est + 1.96 * unname(se),
       n = as.integer(n))
}

#' @export
print.structural_audit <- function(x, ...) {
  a <- x$analysis; e <- x$estimate
  cat("structural audit (core spec ", SPEC_VERSION, ")\n", sep = "")
  cat("  estimand : ", a$estimand, "\n", sep = "")
  cat("  estimator: ", a$estimator, " on ", a$scale, "\n", sep = "")
  cat(sprintf("  estimate : %.3f [%.3f, %.3f], n = %d\n",
              e$value, e$ci_low, e$ci_high, e$n))
  if (length(x$ledger) > 0) {
    cat("  ledger   :\n")
    for (l in x$ledger) {
      v <- if (isTRUE(l$tested)) paste0(" -> ", gsub("_", " ", l$verdict)) else
           if (l$status == "assumed") " (untested)" else ""
      cat("    [", l$status, "] ", l$invariance, v, "\n", sep = "")
    }
  }
  if (length(x$tests) > 0) {
    cat("  attacks  :\n")
    for (t in x$tests)
      cat("    ", t$test, " -> ", gsub("_", " ", t$verdict), "\n", sep = "")
  }
  if (!is.null(x$decision))
    cat("  decision : ", toupper(x$decision$status), " - ", x$decision$rationale, "\n", sep = "")
  invisible(x)
}
