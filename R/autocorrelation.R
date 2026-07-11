# Spatial autocorrelation attack (AssessLite core spec v0.4, spec/spatial.md).
# spatial_holdout asks whether the mechanism is the same across regions; this asks
# whether observations are spatially INDEPENDENT given the model. Moran's I on the
# outcome-model residuals over a k-nearest-neighbour weight matrix: resolved
# autocorrelation means nearby units share unmodelled structure, the effective
# sample size is smaller than n, and i.i.d.-style intervals overstate precision.

# residuals of the declared outcome model on `data`: martingale for Cox, response
# for GLMs. Named by the row names of the rows actually used (complete cases).
model_residuals <- function(audit, data) {
  a <- audit$analysis
  rhs <- paste(c(a$exposure, a$covariates), collapse = " + ")
  fit <- tryCatch(suppressWarnings({
    if (a$estimator == "coxph") {
      f <- stats::as.formula(paste0("survival::Surv(", a$outcome_cols[1], ", ",
                                    a$outcome_cols[2], ") ~ ", rhs))
      survival::coxph(f, data = data)
    } else {
      f <- stats::as.formula(paste0(a$outcome_cols[1], " ~ ", rhs))
      fam <- if (a$estimator == "glm_binomial") stats::binomial() else stats::gaussian()
      stats::glm(f, data = data, family = fam)
    }
  }), error = function(e) NULL)
  if (is.null(fit)) return(NULL)
  type <- if (a$estimator == "coxph") "martingale" else "response"
  stats::residuals(fit, type = type)
}

# k nearest neighbours by Euclidean distance (O(n^2); fine for registry-scale n)
knn_neighbours <- function(x, y, k) {
  n <- length(x); k <- min(k, n - 1)
  nb <- matrix(0L, n, k)
  for (i in seq_len(n)) {
    d2 <- (x - x[i])^2 + (y - y[i])^2
    d2[i] <- Inf
    nb[i, ] <- order(d2)[seq_len(k)]
  }
  nb
}

# Moran's I with a row-standardised kNN weight matrix, plus its moments under the
# normality assumption (Cliff & Ord), so the test is deterministic given the data.
moran_i <- function(r, nb) {
  n <- length(r); k <- ncol(nb)
  z <- r - mean(r)
  zlag <- rowMeans(matrix(z[nb], nrow = n))
  I <- sum(z * zlag) / sum(z^2)                       # S0 = n for row-standardised W
  w <- 1 / k
  S0 <- n
  # reciprocal edges: w_ji > 0 iff i is among j's neighbours
  recip <- matrix(FALSE, n, k)
  for (col in seq_len(k)) {
    j <- nb[, col]
    recip[, col] <- vapply(seq_len(n), function(i) any(nb[j[i], ] == i), logical(1))
  }
  # ordered double-sum of (w_ij + w_ji)^2 over all pairs, iterated over edges i->j:
  # each edge contributes its own ordered term; the mirrored (j,i) term is only
  # missing for non-reciprocal edges, where it equals w^2
  ordered_sum <- sum((w + w * recip)^2) + sum((1 - recip) * w^2)
  S1 <- 0.5 * ordered_sum
  in_deg <- tabulate(as.integer(nb), nbins = n)
  S2 <- sum((1 + in_deg * w)^2)
  EI <- -1 / (n - 1)
  EI2 <- (n^2 * S1 - n * S2 + 3 * S0^2) / ((n^2 - 1) * S0^2)
  V <- EI2 - EI^2
  list(I = I, expected = EI, se = sqrt(V))
}

test_spatial_autocorrelation <- function(audit, k = 8, i_floor = 0.1) {
  coords <- audit$structure$coords
  if (is.null(coords))
    stop("spatial_autocorrelation needs declared coordinates; pass coords = c(x, y) to structural_audit()")
  d <- audit$data
  r <- model_residuals(audit, d)

  empty_variants <- data.frame(label = character(), estimate = numeric(), se = numeric(),
                               ci_low = numeric(), ci_high = numeric(), n = integer(),
                               stringsAsFactors = FALSE)
  mk <- function(verdict, reading, ac) list(
    test = "spatial_autocorrelation", invariance = "spatial_independence", verdict = verdict,
    metrics = NULL, autocorrelation = ac, variants = empty_variants, n_failed = 0L,
    reading = reading)

  if (is.null(r))
    return(mk("not_resolvable",
              "the outcome model could not be fitted, so residual spatial autocorrelation is not resolvable",
              list(moran_i = NA_real_, expected = NA_real_, se = NA_real_, z = NA_real_,
                   p_value = NA_real_, k = k, n = NA_integer_, residual_type = NA_character_)))

  # align residuals (complete cases, named by row name) with coordinates
  pos <- match(names(r), rownames(d))
  ok <- !is.na(pos)
  r <- r[ok]; pos <- pos[ok]
  x <- d[[coords[1]]][pos]; y <- d[[coords[2]]][pos]
  keep <- !is.na(x) & !is.na(y)
  r <- r[keep]; x <- x[keep]; y <- y[keep]
  n <- length(r)
  rtype <- if (audit$analysis$estimator == "coxph") "martingale" else "response"
  if (n < 30)
    return(mk("not_resolvable",
              sprintf("only %d units have residuals and coordinates; spatial independence is not resolvable", n),
              list(moran_i = NA_real_, expected = NA_real_, se = NA_real_, z = NA_real_,
                   p_value = NA_real_, k = k, n = n, residual_type = rtype)))

  nb <- knn_neighbours(x, y, k)
  m <- moran_i(r, nb)
  z <- (m$I - m$expected) / m$se
  p <- 2 * stats::pnorm(-abs(z))
  mdi <- 1.96 * m$se                                   # smallest I resolvable at this n

  verdict <- if (p < 0.05 && abs(m$I) >= i_floor) "unstable"
             else if (mdi > i_floor) "not_resolvable" else "stable"
  ac <- list(moran_i = round(m$I, 4), expected = round(m$expected, 4), se = round(m$se, 4),
             z = round(z, 3), p_value = round(p, 4), k = as.integer(ncol(nb)), n = n,
             residual_type = rtype)
  reading <- switch(verdict,
    unstable = sprintf(paste0("the outcome-model residuals are spatially autocorrelated (Moran's I ",
      "%.3f over %d-nearest-neighbour weights, p = %.2g): nearby units share unmodelled structure, ",
      "the effective sample size is smaller than n = %d, and intervals that treat units as ",
      "independent overstate precision (%s residuals; normality-based test)"),
      m$I, ncol(nb), p, n, rtype),
    stable = sprintf(paste0("no resolved spatial autocorrelation in the outcome-model residuals ",
      "(Moran's I %.3f, p = %.2g; the test could resolve I of about %.3f at this n); treating units ",
      "as spatially independent holds up (%s residuals)"),
      m$I, p, mdi, rtype),
    not_resolvable = sprintf(paste0("the test could only resolve Moran's I of about %.3f at this ",
      "n and configuration, above the %.2f floor; spatial independence can neither be shown nor ",
      "ruled out"), mdi, i_floor))
  mk(verdict, reading, ac)
}
