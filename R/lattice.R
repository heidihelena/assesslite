# Assumption lattice (AssessLite core spec v0.2, spec/lattice.md).
# The pooling invariances (pool across clusters / time) are the "stronger symmetry
# -> one number" commitments. This refits the exposure estimate under every
# pool-or-stratify combination and reports whether the conclusion depends on those
# pooling commitments. Nodes are ordered by how much is pooled; the top node (pool
# everything) is the main estimate, the bottom node (stratify everything) makes the
# weakest pooling assumptions.

#' Build the pooling assumption lattice
#'
#' @param audit a structural_audit object (with a fitted estimate).
#' @return the audit with a $lattice element.
assumption_lattice <- function(audit) {
  stopifnot(inherits(audit, "structural_audit"))
  s <- audit$structure
  axis_invariance <- character()
  axis_var <- character()
  if (!is.null(s$cluster)) { axis_invariance <- c(axis_invariance, "cluster_exchangeability"); axis_var <- c(axis_var, s$cluster) }
  if (!is.null(s$time))    { axis_invariance <- c(axis_invariance, "temporal_translation");   axis_var <- c(axis_var, s$time) }
  names(axis_var) <- axis_invariance
  axes <- axis_invariance

  if (length(axes) == 0) {
    audit$lattice <- list(axes = character(), variables = list(), nodes = list(),
      verdict = "not_resolvable",
      reading = "no poolable structural axes (cluster or time) were declared; the pooling lattice is empty")
    return(audit)
  }

  main <- audit$estimate
  k <- length(axes)
  subsets <- lapply(0:(2^k - 1), function(m) axes[bitwAnd(m, 2^(seq_len(k) - 1)) > 0])
  nodes <- list()
  for (P in subsets) {
    stratified <- setdiff(axes, P)
    fit <- fit_estimate(audit, audit$data, strata = unname(axis_var[stratified]))
    if (is.null(fit)) next
    same_sign <- sign(fit$value) == sign(main$value) || sign(main$value) == 0
    excl_null <- fit$ci_low > 0 || fit$ci_high < 0
    status <- if (!same_sign && excl_null) "reversed"
              else if (!excl_null) "attenuated"
              else "consistent"
    nodes[[length(nodes) + 1]] <- list(
      pooled = I(as.character(P)), stratified = I(as.character(stratified)),
      n_pooled = length(P), estimate = fit$value,
      ci_low = fit$ci_low, ci_high = fit$ci_high, n = fit$n, status = status)
  }

  statuses <- vapply(nodes, function(x) x$status, character(1))
  verdict <- if (any(statuses == "reversed")) "unstable"
             else if (any(statuses == "attenuated")) "not_resolvable"
             else "stable"
  axis_words <- gsub("_", " ", axes)
  reading <- switch(verdict,
    stable = sprintf(paste0("the exposure estimate keeps the same direction and stays distinguishable ",
      "from no effect under every pool-or-stratify choice over {%s}; the conclusion does not depend on ",
      "these pooling commitments"), paste(axis_words, collapse = ", ")),
    not_resolvable = sprintf(paste0("under some pool-or-stratify choices over {%s} the interval comes to ",
      "include no effect: the direction holds throughout, but whether the effect is resolved depends on ",
      "the pooling commitments"), paste(axis_words, collapse = ", ")),
    unstable = sprintf(paste0("the exposure estimate changes sign under some pool-or-stratify choice over ",
      "{%s}; the conclusion depends on these pooling commitments and does not hold across the lattice"),
      paste(axis_words, collapse = ", ")))

  audit$lattice <- list(axes = axes, variables = as.list(axis_var), nodes = nodes,
                        verdict = verdict, reading = reading)
  audit
}
