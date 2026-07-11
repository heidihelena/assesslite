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

#' Declare a causal DAG for the graph_check and adjustment_check attacks
#'
#' @param audit a structural_audit object.
#' @param edges character vector of directed edges, e.g. c("age -> adherence",
#'   "stage -> survival"). Nodes are the union of everything named.
#' @param latent character vector of node names that are part of the causal
#'   structure but not measured (e.g. an unmeasured confounder). Latent nodes may
#'   not enter an adjustment set, and implications that touch them are not testable.
declare_graph <- function(audit, edges, latent = character()) {
  stopifnot(inherits(audit, "structural_audit"))
  g <- parse_graph(edges)
  bad_latent <- setdiff(latent, g$nodes)
  if (length(bad_latent) > 0)
    stop("latent nodes not in the graph: ", paste(bad_latent, collapse = ", "))
  g$latent <- latent
  # observed graph nodes absent from the data (excluding the ones declared latent)
  missing <- setdiff(setdiff(g$nodes, latent), names(audit$data))
  if (length(missing) > 0)
    warning("graph nodes not found in the data and not declared latent ",
            "(implications involving them will be skipped): ", paste(missing, collapse = ", "))
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
  latent <- if (is.null(g$latent)) character() else g$latent
  observed <- function(v) !(v %in% latent) && (v %in% names(d))
  imps <- list()

  for (i in seq_along(ord)) {
    V <- ord[i]
    preds <- ord[seq_len(i - 1)]
    par <- parents[[V]]
    for (W in setdiff(preds, par)) {
      cond <- par
      claim <- sprintf("%s _||_ %s | {%s}", V, W, paste(cond, collapse = ", "))
      # an implication is testable only if both endpoints and every conditioning
      # node are observed (not latent, present in the data)
      testable <- observed(V) && observed(W) && all(vapply(cond, observed, logical(1)))
      vv <- if (testable) coerce_numeric(d[[V]]) else NULL
      ww <- if (testable) coerce_numeric(d[[W]]) else NULL
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

# --- d-separation and the backdoor criterion (core spec v0.2, spec/graph/adjustment.md) ---

# children map from a parents map
children_of <- function(parents) {
  ch <- stats::setNames(vector("list", length(parents)), names(parents))
  for (v in names(parents)) for (p in parents[[v]]) ch[[p]] <- c(ch[[p]], v)
  ch
}

# all ancestors of a set S (inclusive), following parents upward
ancestors_of <- function(parents, S) {
  seen <- character(0); stack <- S
  while (length(stack) > 0) {
    v <- stack[1]; stack <- stack[-1]
    if (v %in% seen) next
    seen <- c(seen, v)
    stack <- c(stack, parents[[v]])
  }
  unique(seen)
}

# all descendants of a single node (exclusive of itself)
descendants_of <- function(parents, node) {
  ch <- children_of(parents)
  seen <- character(0); stack <- ch[[node]]
  while (length(stack) > 0) {
    v <- stack[1]; stack <- stack[-1]
    if (v %in% seen) next
    seen <- c(seen, v); stack <- c(stack, ch[[v]])
  }
  unique(seen)
}

# d-separation by the moralised ancestral graph (Lauritzen): are X and Y
# d-separated given Z in the DAG described by `parents`?
d_separated <- function(parents, X, Y, Z) {
  A <- ancestors_of(parents, unique(c(X, Y, Z)))
  # undirected adjacency among A: parent-child edges + moral (co-parent) edges
  adj <- stats::setNames(lapply(A, function(x) character(0)), A)
  link <- function(a, b) { adj[[a]] <<- union(adj[[a]], b); adj[[b]] <<- union(adj[[b]], a) }
  for (v in A) {
    pv <- intersect(parents[[v]], A)
    for (p in pv) link(v, p)
    if (length(pv) > 1) for (i in seq_len(length(pv) - 1)) for (j in (i + 1):length(pv)) link(pv[i], pv[j])
  }
  # remove Z, then test X-Y connectivity
  keep <- setdiff(A, Z)
  if (!(X %in% keep) || !(Y %in% keep)) return(TRUE)
  seen <- character(0); stack <- X
  while (length(stack) > 0) {
    v <- stack[1]; stack <- stack[-1]
    if (v %in% seen) next
    seen <- c(seen, v)
    stack <- c(stack, intersect(adj[[v]], keep))
  }
  !(Y %in% seen)
}

# Z satisfies the backdoor criterion for X -> Y: no z is a descendant of X, and
# Z d-separates X from Y in the graph with X's outgoing edges removed.
backdoor_valid <- function(parents, X, Y, Z) {
  desc <- descendants_of(parents, X)
  if (length(intersect(Z, desc)) > 0) return(FALSE)
  parents_xbar <- parents
  for (v in names(parents_xbar)) parents_xbar[[v]] <- setdiff(parents_xbar[[v]], X)
  d_separated(parents_xbar, X, Y, Z)
}

# adjustment_check: given the declared graph, does the adjusted covariate set
# satisfy the backdoor criterion for exposure -> outcome?
test_adjustment_check <- function(audit, outcome_node = NULL) {
  g <- audit$graph
  if (is.null(g)) stop("adjustment_check needs a declared graph; call declare_graph() first")
  X <- audit$analysis$exposure
  oc <- audit$analysis$outcome_cols
  if (is.null(outcome_node)) {
    cand <- if (length(oc) == 2) c(oc[2], oc[1]) else oc[1]
    outcome_node <- cand[cand %in% g$nodes][1]
  }
  Y <- outcome_node
  adjusted <- audit$analysis$covariates

  empty_variants <- data.frame(label = character(), estimate = numeric(), se = numeric(),
                               ci_low = numeric(), ci_high = numeric(), n = integer(),
                               stringsAsFactors = FALSE)
  mk <- function(verdict, reading, adj) list(
    test = "adjustment_check", invariance = "adjustment_sufficiency", verdict = verdict,
    metrics = NULL, adjustment = adj, variants = empty_variants, n_failed = 0L, reading = reading)

  if (is.na(Y) || !(X %in% g$nodes) || !(Y %in% g$nodes)) {
    return(mk("not_resolvable",
      sprintf("cannot check the adjustment set: exposure '%s' or outcome '%s' is not a node in the declared graph",
              X, if (is.na(Y)) "<none>" else Y),
      list(exposure = X, outcome = if (is.na(Y)) NA_character_ else Y,
           adjusted = I(as.character(adjusted)), sufficient_set = I(character(0)),
           valid = NA, identifiable = NA, open_backdoor = NA,
           over_adjustment = I(character(0)), missing = I(character(0)))))
  }

  latent <- if (is.null(g$latent)) character() else g$latent
  observed <- setdiff(g$nodes, latent)
  Z <- intersect(adjusted, observed)
  desc_X <- descendants_of(g$parents, X)
  over <- intersect(adjusted, desc_X)
  parents_xbar <- g$parents
  for (v in names(parents_xbar)) parents_xbar[[v]] <- setdiff(parents_xbar[[v]], X)
  open_backdoor <- !d_separated(parents_xbar, X, Y, Z)
  valid <- (length(over) == 0) && !open_backdoor

  # canonical observed adjustment set (van der Zander et al.): a valid adjustment
  # set exists iff this one is valid. Ancestors of X or Y, observed, not X/Y and
  # not descendants of X.
  z_all <- setdiff(intersect(ancestors_of(g$parents, c(X, Y)), observed), c(X, Y, desc_X))
  identifiable <- backdoor_valid(g$parents, X, Y, z_all)

  # minimal sufficient set: greedily reduce the canonical set
  suff <- z_all
  if (identifiable) {
    changed <- TRUE
    while (changed) {
      changed <- FALSE
      for (z in suff) {
        if (backdoor_valid(g$parents, X, Y, setdiff(suff, z))) { suff <- setdiff(suff, z); changed <- TRUE; break }
      }
    }
  }
  missing <- setdiff(suff, Z)

  adj <- list(exposure = X, outcome = Y,
              adjusted = I(as.character(adjusted)),
              sufficient_set = I(as.character(if (identifiable) suff else character(0))),
              valid = valid && identifiable, identifiable = identifiable,
              open_backdoor = open_backdoor,
              over_adjustment = I(as.character(over)),
              missing = I(as.character(missing)))

  if (!identifiable) {
    lat_txt <- if (length(latent) > 0) sprintf(" (e.g. through the unmeasured node(s) {%s})",
                                               paste(latent, collapse = ", ")) else ""
    reading <- sprintf(paste0("given the declared graph, the effect of %s on %s is not identifiable by ",
      "adjusting for measured covariates: a backdoor path cannot be blocked by any observed set%s. ",
      "No adjustment is sufficient; this is not resolvable by covariate adjustment"), X, Y, lat_txt)
    return(mk("not_resolvable", reading, adj))
  }
  if (valid) {
    reading <- sprintf(paste0("the adjusted covariates {%s} satisfy the backdoor criterion for %s -> %s ",
      "in the declared graph; the adjustment agrees with the graph (a sufficient set is {%s})"),
      paste(Z, collapse = ", "), X, Y, if (length(suff)) paste(suff, collapse = ", ") else "empty")
    return(mk("stable", reading, adj))
  }
  problems <- c(
    if (open_backdoor) sprintf("a backdoor path from %s to %s is left open (missing: {%s})",
                               X, Y, if (length(missing)) paste(missing, collapse = ", ") else "unclear") else NULL,
    if (length(over) > 0) sprintf("it conditions on {%s}, which is a descendant of the exposure (over-adjustment / collider or mediator bias)",
                                  paste(over, collapse = ", ")) else NULL)
  reading <- sprintf("the adjustment does not agree with the declared graph: %s. A sufficient set per the graph is {%s}",
                     paste(problems, collapse = "; and "),
                     if (length(suff)) paste(suff, collapse = ", ") else "empty")
  mk("unstable", reading, adj)
}
