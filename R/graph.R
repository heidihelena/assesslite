# Causal-graph check (AssessLite core spec v0.2, spec/graph/graph-check.md).
# Declares a DAG, derives its implied conditional independencies (ordered local
# Markov), and tests each against the data by partial correlation. Self-contained
# base R; no external graph package.

# Parse edges like "age -> adherence" into nodes, a parents map, and a topological
# order. Errors if the declared graph is cyclic.
parse_graph <- function(edges) {
  if (length(edges) == 0) stop("declare_graph() needs at least one edge like 'a -> b'")
  from <- to <- character(0)
  for (e in edges) {
    parts <- trimws(strsplit(e, "->", fixed = TRUE)[[1]])
    if (length(parts) != 2 || any(!nzchar(parts)))
      stop("edge '", e, "' is not of the form 'a -> b'")
    from <- c(from, parts[1]); to <- c(to, parts[2])
  }
  nodes <- unique(c(from, to))
  parents <- stats::setNames(lapply(nodes, function(v) unique(from[to == v])), nodes)
  # Kahn-style topological order
  placed <- character(0); remaining <- nodes
  while (length(remaining) > 0) {
    ready <- remaining[vapply(remaining, function(v) all(parents[[v]] %in% placed), logical(1))]
    if (length(ready) == 0) stop("the declared graph is not acyclic")
    placed <- c(placed, ready); remaining <- setdiff(remaining, ready)
  }
  list(edges = edges, nodes = nodes, parents = parents, order = placed)
}

#' Declare a causal DAG for the graph_check attack
#'
#' @param audit a structural_audit object.
#' @param edges character vector of directed edges, e.g. c("age -> adherence",
#'   "stage -> survival"). Nodes are the union of everything named.
declare_graph <- function(audit, edges) {
  stopifnot(inherits(audit, "structural_audit"))
  g <- parse_graph(edges)
  missing <- setdiff(g$nodes, names(audit$data))
  if (length(missing) > 0)
    warning("graph nodes not found in the data (implications involving them will be skipped): ",
            paste(missing, collapse = ", "))
  audit$graph <- g
  audit
}

# Coerce a variable to a single numeric column, or NULL if it is a multi-level
# categorical (not testable as an endpoint of an independence claim).
coerce_numeric <- function(x) {
  if (is.logical(x)) return(as.numeric(x))
  if (is.numeric(x)) return(as.numeric(x))
  u <- sort(unique(as.character(x[!is.na(x)])))
  if (length(u) == 2) return(as.numeric(factor(as.character(x), levels = u)) - 1)
  NULL
}

# Partial correlation of v and w given conditioning frame Z (may be NULL/empty).
partial_cor <- function(v, w, Z) {
  if (is.null(Z) || ncol(Z) == 0) {
    ok <- stats::complete.cases(v, w)
    v <- v[ok]; w <- w[ok]
    rv <- v - mean(v); rw <- w - mean(w); k <- 0L
  } else {
    ok <- stats::complete.cases(v, w, Z)
    v <- v[ok]; w <- w[ok]; Z <- Z[ok, , drop = FALSE]
    for (j in seq_along(Z)) if (is.character(Z[[j]])) Z[[j]] <- factor(Z[[j]])
    mm <- stats::model.matrix(~ ., data = Z)
    fv <- stats::lm.fit(mm, v); fw <- stats::lm.fit(mm, w)
    rv <- fv$residuals; rw <- fw$residuals; k <- fv$rank - 1L
  }
  n <- length(v)
  r <- suppressWarnings(stats::cor(rv, rw))
  list(r = r, n = n, k = k)
}

# graph_check: attacks the causal_graph invariance by testing the DAG's implied
# conditional independencies against the data.
test_graph_check <- function(audit, alpha = 0.05, effect_floor = 0.1) {
  g <- audit$graph
  if (is.null(g)) stop("graph_check needs a declared graph; call declare_graph() first")
  d <- audit$data; ord <- g$order; parents <- g$parents
  imps <- list()

  for (i in seq_along(ord)) {
    V <- ord[i]
    preds <- ord[seq_len(i - 1)]
    par <- parents[[V]]
    for (W in setdiff(preds, par)) {
      cond <- par
      claim <- sprintf("%s _||_ %s | {%s}", V, W, paste(cond, collapse = ", "))
      vv <- if (V %in% names(d)) coerce_numeric(d[[V]]) else NULL
      ww <- if (W %in% names(d)) coerce_numeric(d[[W]]) else NULL
      if (is.null(vv) || is.null(ww)) {
        imps[[length(imps) + 1]] <- list(claim = claim, conditioning = cond,
          partial_r = NA_real_, p_value = NA_real_, n = NA_integer_, status = "not_testable")
        next
      }
      Z <- if (length(cond) > 0) d[cond] else NULL
      pc <- partial_cor(vv, ww, Z)
      dfree <- pc$n - pc$k - 3
      if (!is.finite(pc$r) || dfree < 1) {
        status <- "not_resolvable"; p <- NA_real_
      } else {
        z <- atanh(pmax(pmin(pc$r, 1 - 1e-12), -1 + 1e-12)) * sqrt(dfree)
        p <- 2 * stats::pnorm(-abs(z))
        mds <- tanh(1.96 / sqrt(dfree))
        status <- if (p < alpha && abs(pc$r) >= effect_floor) "violated"
                  else if (mds > effect_floor) "not_resolvable" else "consistent"
      }
      imps[[length(imps) + 1]] <- list(claim = claim, conditioning = cond,
        partial_r = round(pc$r, 4), p_value = if (is.na(p)) NA_real_ else round(p, 4),
        n = pc$n, status = status)
    }
  }

  statuses <- vapply(imps, function(x) x$status, character(1))
  n_testable <- sum(statuses != "not_testable")
  verdict <- if (any(statuses == "violated")) "unstable"
             else if (n_testable == 0 || any(statuses == "not_resolvable")) "not_resolvable"
             else "stable"
  n_viol <- sum(statuses == "violated")
  reading <- switch(verdict,
    unstable = sprintf(paste0("the data contradict %d of the graph's %d implied independencies ",
      "(e.g. %s), so the declared causal graph does not hold up (partial-correlation test, a ",
      "linear approximation to conditional independence)"),
      n_viol, n_testable,
      imps[[which(statuses == "violated")[1]]]$claim),
    not_resolvable = if (n_testable == 0)
      "none of the graph's implied independencies were testable at this n (endpoints were multi-level categoricals); the graph is not resolvable against this data"
      else sprintf(paste0("no implied independence was contradicted, but at least one of the %d ",
        "testable implications was underpowered; the graph is not fully resolvable at this n"), n_testable),
    stable = sprintf(paste0("every one of the %d testable implied independencies is consistent with ",
      "the data (partial-correlation test); the data do not contradict the declared graph. This does ",
      "not establish the graph — Markov-equivalent graphs share these implications"), n_testable))

  list(test = "graph_check", invariance = "causal_graph", verdict = verdict, metrics = NULL,
       implications = imps,
       variants = data.frame(label = character(), estimate = numeric(), se = numeric(),
                             ci_low = numeric(), ci_high = numeric(), n = integer(),
                             stringsAsFactors = FALSE),
       n_failed = 0L, reading = reading)
}
