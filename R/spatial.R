# Spatial attack (AssessLite core spec v0.3, spec/spatial.md).
# Attacks the spatial_translation invariance (the mechanism is the same across the
# field) by leave-one-spatial-block-out: grid the coordinate space into k x k blocks
# and refit with each block removed. A material shift means some region drives the
# estimate — the mechanism is not spatially stationary.

# assign each row to a k x k grid block from quantile bins of the two coordinates
spatial_blocks <- function(x, y, k) {
  qb <- function(v) {
    br <- unique(stats::quantile(v, seq(0, 1, length.out = k + 1), na.rm = TRUE))
    if (length(br) < 2) return(rep(1L, length(v)))
    cut(v, breaks = br, include.lowest = TRUE, labels = FALSE)
  }
  bx <- qb(x); by <- qb(y)
  ifelse(is.na(bx) | is.na(by), NA_character_, paste0(bx, "_", by))
}

test_spatial_holdout <- function(audit, k = 3) {
  coords <- audit$structure$coords
  if (is.null(coords))
    stop("spatial_holdout needs declared coordinates; pass coords = c(x, y) to structural_audit()")
  d <- audit$data
  block <- spatial_blocks(d[[coords[1]]], d[[coords[2]]], k)
  rows <- list(); n_failed <- 0
  for (b in sort(unique(block[!is.na(block)]))) {
    keep <- is.na(block) | block != b
    fit <- fit_estimate(audit, d[keep, , drop = FALSE])
    if (is.null(fit)) { n_failed <- n_failed + 1; next }
    rows[[length(rows) + 1]] <- data.frame(
      label = paste0("without spatial block ", b), estimate = fit$value, se = fit$se,
      ci_low = fit$ci_low, ci_high = fit$ci_high, n = fit$n, stringsAsFactors = FALSE)
  }
  variants <- if (length(rows)) do.call(rbind, rows) else
    data.frame(label = character(), estimate = numeric(), se = numeric(),
               ci_low = numeric(), ci_high = numeric(), n = integer(), stringsAsFactors = FALSE)
  build_test_result(audit, "spatial_holdout", "spatial_translation", variants, n_failed)
}
