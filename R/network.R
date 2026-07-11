# Network interference attack (AssessLite core spec v0.3, spec/network.md).
# Attacks the network_relabelling invariance (relabelling nodes, preserving graph
# structure, leaves the mechanism unchanged) by testing whether the outcome depends
# on neighbours' exposure. A resolved neighbour-exposure effect is interference:
# who is adjacent to whom matters, so relabelling changes the mechanism (SUTVA fails).

# mean exposure among each unit's neighbours (units present in the data); NA if none
neighbor_exposure <- function(ids, xvec, edges) {
  a <- as.character(edges[[1]]); b <- as.character(edges[[2]])
  from <- c(a, b); to <- c(b, a)                       # undirected
  keep <- from %in% ids & to %in% ids
  from <- from[keep]; to <- to[keep]
  ne <- stats::setNames(rep(NA_real_, length(ids)), ids)
  if (length(from) > 0) {
    m <- tapply(xvec[to], from, mean)
    ne[names(m)] <- as.numeric(m)
  }
  ne
}

test_interference <- function(audit) {
  net <- audit$network
  if (is.null(net))
    stop("interference_check needs a network; pass unit_id and edges to structural_audit()")
  d <- audit$data
  ids <- as.character(d[[net$unit_id]])
  xvec <- stats::setNames(d[[audit$analysis$exposure]], ids)
  ne <- neighbor_exposure(ids, xvec, net$edges)
  n_with_nb <- sum(!is.na(ne))
  ne[is.na(ne)] <- mean(xvec, na.rm = TRUE)            # neutral impute for no-neighbour units

  d2 <- d; d2$neighbor_exposure <- as.numeric(ne)
  mod <- audit
  mod$analysis$covariates <- c(audit$analysis$covariates, "neighbor_exposure")
  fit_x  <- fit_estimate(mod, d2)
  fit_nb <- fit_estimate(mod, d2, coef_of = "neighbor_exposure")

  empty_variants <- data.frame(label = character(), estimate = numeric(), se = numeric(),
                               ci_low = numeric(), ci_high = numeric(), n = integer(),
                               stringsAsFactors = FALSE)
  mk <- function(verdict, reading, sp) list(
    test = "interference_check", invariance = "network_relabelling", verdict = verdict,
    metrics = NULL, spillover = sp, variants = empty_variants, n_failed = 0L, reading = reading)

  if (is.null(fit_nb) || is.null(fit_x)) {
    return(mk("not_resolvable",
      "the neighbour-exposure model could not be fitted; interference is not resolvable with this data",
      list(neighbor_exposure_coef = NA_real_, ci_low = NA_real_, ci_high = NA_real_,
           exposure_estimate = audit$estimate$value, exposure_estimate_adjusted = NA_real_,
           n_with_neighbors = n_with_nb)))
  }

  excl_null <- fit_nb$ci_low > 0 || fit_nb$ci_high < 0
  half <- 1.96 * fit_nb$se
  main_eff <- abs(audit$estimate$value)
  verdict <- if (excl_null) "unstable"
             else if (half > max(main_eff, 0.1)) "not_resolvable" else "stable"

  sp <- list(neighbor_exposure_coef = fit_nb$value, ci_low = fit_nb$ci_low,
             ci_high = fit_nb$ci_high, exposure_estimate = audit$estimate$value,
             exposure_estimate_adjusted = fit_x$value, n_with_neighbors = n_with_nb)

  reading <- switch(verdict,
    unstable = sprintf(paste0("the outcome depends on neighbours' exposure (neighbour-exposure effect ",
      "%.3f [%.3f, %.3f], distinguishable from zero): interference is present, so relabelling the network ",
      "changes the mechanism and SUTVA does not hold. The exposure estimate is %.3f ignoring neighbours vs ",
      "%.3f accounting for them"),
      fit_nb$value, fit_nb$ci_low, fit_nb$ci_high, audit$estimate$value, fit_x$value),
    stable = sprintf(paste0("no detectable dependence on neighbours' exposure (neighbour-exposure effect ",
      "%.3f [%.3f, %.3f], not distinguishable from zero and smaller than the exposure effect); the mechanism ",
      "holds up under network relabelling at this n"),
      fit_nb$value, fit_nb$ci_low, fit_nb$ci_high),
    not_resolvable = sprintf(paste0("the neighbour-exposure effect could not be resolved at this n ",
      "(interval half-width %.3f exceeds the exposure effect %.3f); interference can neither be shown nor ruled out"),
      half, main_eff))

  mk(verdict, reading, sp)
}
