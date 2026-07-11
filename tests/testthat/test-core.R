simulate_cohort <- function(n = 600, effect = -0.4, seed = 1) {
  set.seed(seed)
  hospital <- sample(sprintf("H%d", 1:6), n, replace = TRUE)
  year <- sample(2018:2023, n, replace = TRUE)
  age <- rnorm(n, 65, 8)
  x <- rbinom(n, 1, plogis(-0.02 * (age - 65)))
  y <- rbinom(n, 1, plogis(-1 + 0.04 * (age - 65) + effect * x))
  data.frame(hospital, year, age, x, y)
}

open_audit <- function(d) {
  structural_audit(d, outcome = "y", exposure = "x", covariates = "age",
                   cluster = "hospital", time = "year", unit = "patient")
}

test_that("constructor fits the full-sample estimate and detects binomial outcome", {
  a <- open_audit(simulate_cohort())
  expect_s3_class(a, "structural_audit")
  expect_equal(a$analysis$estimator, "glm_binomial")
  expect_true(is.finite(a$estimate$value))
  expect_lt(a$estimate$value, 0)
})

test_that("ledger enforces the core vocabulary and requires rationale and licence", {
  a <- open_audit(simulate_cohort())
  expect_error(assume_invariance(a, "my_new_symmetry", "r", "l"), "vocabulary")
  expect_error(assume_invariance(a, "cluster_exchangeability", "", "l"), "rationale")
  expect_error(assume_invariance(a, "cluster_exchangeability", "r", ""), "licence")
  a <- assume_invariance(a, "cluster_exchangeability", "same guideline", "pooling")
  expect_error(assume_invariance(a, "cluster_exchangeability", "again", "again"),
               "already in the ledger")
})

test_that("verdict rule is three-way and matches the spec", {
  v <- data.frame(label = "a", estimate = 0.5, se = 0.1,
                  ci_low = 0.3, ci_high = 0.7, n = 100L)
  m <- stability_metrics(0.5, 0.1, 0.3, 0.7, v)
  expect_equal(verdict_from_metrics(m, 0.5, 0.1), "stable")

  v2 <- data.frame(label = "a", estimate = -0.5, se = 0.1,
                   ci_low = -0.7, ci_high = -0.3, n = 100L)
  m2 <- stability_metrics(0.5, 0.1, 0.3, 0.7, v2)
  expect_equal(verdict_from_metrics(m2, 0.5, 0.1), "unstable")

  v3 <- data.frame(label = "a", estimate = 0.5, se = 2.0,
                   ci_low = -3.4, ci_high = 4.4, n = 20L)
  m3 <- stability_metrics(0.5, 0.1, 0.3, 0.7, v3)
  expect_equal(verdict_from_metrics(m3, 0.5, 0.1), "not_resolvable")
})

test_that("unit permutation is stable for an order-symmetric estimator", {
  a <- open_audit(simulate_cohort())
  a <- assume_invariance(a, "unit_permutation_within_cluster",
                         "ordering carries no information", "pooling within cluster")
  a <- test_invariance(a, tests = "unit_permutation", seed = 3)
  expect_equal(a$tests$unit_permutation$verdict, "stable")
})

test_that("rejected invariances are not tested against", {
  a <- open_audit(simulate_cohort())
  a <- reject_invariance(a, "cluster_exchangeability",
                         "hospitals differ by design", "cluster enters as structure")
  expect_warning(a <- test_invariance(a, tests = "cluster_holdout"), "rejected")
  expect_length(a$tests, 0)
})

test_that("decision abstains on a resolved instability and reports the breaker", {
  d <- simulate_cohort(n = 2000, effect = -0.6, seed = 2)
  # one hospital with a strong opposite mechanism: cluster exchangeability is false
  flip <- d$hospital == "H1"
  d$y[flip] <- rbinom(sum(flip), 1, plogis(-1 + 2.5 * d$x[flip]))
  a <- open_audit(d)
  a <- assume_invariance(a, "cluster_exchangeability", "assumed provisionally", "pooling")
  a <- test_invariance(a, tests = "cluster_holdout")
  a <- decide(a)
  expect_equal(a$decision$status, "abstain")
  expect_equal(a$decision$broken_by, "cluster_holdout")
})

test_that("untested assumed invariances cap the decision at conditional", {
  a <- open_audit(simulate_cohort())
  a <- assume_invariance(a, "temporal_translation", "no revisions in window", "pooling years")
  a <- assume_invariance(a, "cluster_exchangeability", "same guideline", "pooling clusters")
  a <- test_invariance(a, tests = "cluster_holdout")
  a <- decide(a)
  expect_true(a$decision$status %in% c("conditional", "abstain"))
  if (a$decision$status == "conditional")
    expect_true("temporal_translation" %in% a$decision$exposed_surface)
})

test_that("positivity_check reads good overlap as stable and poor overlap as not resolvable", {
  set.seed(1); n <- 2500; age <- rnorm(n)
  x1 <- rbinom(n, 1, plogis(0.3 * age))
  d1 <- data.frame(y = rbinom(n, 1, plogis(-0.6 * x1 + 0.3 * age)), x = x1, age = age)
  a1 <- structural_audit(d1, outcome = "y", exposure = "x", covariates = "age")
  a1 <- test_invariance(assume_invariance(a1, "positivity", "p", "o"), tests = "positivity_check")
  expect_equal(a1$tests$positivity_check$verdict, "stable")
  expect_lt(a1$tests$positivity_check$overlap$frac_extreme, 0.05)

  set.seed(5); z <- rnorm(n); x2 <- rbinom(n, 1, plogis(2.8 * z))
  d2 <- data.frame(y = rbinom(n, 1, plogis(-0.6 * x2 + 0.5 * z)), x = x2, z = z)
  a2 <- structural_audit(d2, outcome = "y", exposure = "x", covariates = "z")
  a2 <- test_invariance(assume_invariance(a2, "positivity", "p", "o"), tests = "positivity_check")
  expect_equal(a2$tests$positivity_check$verdict, "not_resolvable")
  expect_gt(a2$tests$positivity_check$overlap$frac_extreme, 0.10)
})

test_that("positivity_check needs a binary exposure and covariates", {
  d <- data.frame(y = rbinom(60, 1, .5), x = rnorm(60), age = rnorm(60))
  a <- structural_audit(d, outcome = "y", exposure = "x", covariates = "age")
  expect_error(test_invariance(a, tests = "positivity_check"), "binary")
  d2 <- data.frame(y = rbinom(60, 1, .5), x = rbinom(60, 1, .5))
  a2 <- structural_audit(d2, outcome = "y", exposure = "x")
  expect_error(test_invariance(a2, tests = "positivity_check"), "covariates")
})

test_that("interference_check detects spillover and passes a non-interfering network", {
  set.seed(1); n <- 1500
  ids <- paste0("u", seq_len(n))
  m <- n * 3; ea <- sample(ids, m, TRUE); eb <- sample(ids, m, TRUE); keep <- ea != eb
  edges <- data.frame(a = ea[keep], b = eb[keep])
  x <- rbinom(n, 1, 0.5); names(x) <- ids
  ne <- neighbor_exposure(ids, x, edges); ne[is.na(ne)] <- mean(x)
  y_int <- rbinom(n, 1, plogis(-0.5 * x + 1.2 * ne))
  d1 <- data.frame(id = ids, x = x, y = y_int)
  a1 <- structural_audit(d1, outcome = "y", exposure = "x", unit_id = "id", edges = edges)
  a1 <- assume_invariance(a1, "network_relabelling", "no interference", "SUTVA")
  a1 <- test_invariance(a1, tests = "interference_check")
  expect_equal(a1$tests$interference_check$verdict, "unstable")
  expect_true(!is.null(a1$tests$interference_check$spillover))

  y_no <- rbinom(n, 1, plogis(-0.5 * x))
  d2 <- data.frame(id = ids, x = x, y = y_no)
  a2 <- structural_audit(d2, outcome = "y", exposure = "x", unit_id = "id", edges = edges)
  a2 <- assume_invariance(a2, "network_relabelling", "n", "p")
  a2 <- test_invariance(a2, tests = "interference_check")
  expect_equal(a2$tests$interference_check$verdict, "stable")
})

test_that("edges require unit_id, uniqueness, and interference_check needs a network", {
  d <- data.frame(id = c("a", "a", "b"), x = c(0, 1, 0), y = c(0, 1, 1))
  edges <- data.frame(a = "a", b = "b")
  expect_error(structural_audit(d, outcome = "y", exposure = "x", unit_id = "id", edges = edges), "unique")
  a <- structural_audit(data.frame(x = rbinom(50, 1, .5), y = rbinom(50, 1, .5)),
                        outcome = "y", exposure = "x")
  expect_error(test_invariance(a, tests = "interference_check"), "needs a network")
})

test_that("spatial_holdout flags regional heterogeneity and passes a stationary field", {
  set.seed(2); n <- 3000
  lon <- runif(n, 0, 10); lat <- runif(n, 0, 10); x <- rbinom(n, 1, 0.5)
  eff <- ifelse(lon < 5, -1.8, 0.0)
  y <- rbinom(n, 1, plogis(0.2 + eff * x))
  d <- data.frame(y = y, x = x, lon = lon, lat = lat)
  a <- structural_audit(d, outcome = "y", exposure = "x", coords = c("lon", "lat"))
  a <- assume_invariance(a, "spatial_translation", "homog", "pool across space")
  a <- test_invariance(a, tests = "spatial_holdout", spatial_k = 2)
  expect_equal(a$tests$spatial_holdout$verdict, "unstable")
  expect_equal(nrow(a$tests$spatial_holdout$variants), 4)

  y2 <- rbinom(n, 1, plogis(-0.6 * x))
  d2 <- data.frame(y = y2, x = x, lon = lon, lat = lat)
  a2 <- structural_audit(d2, outcome = "y", exposure = "x", coords = c("lon", "lat"))
  a2 <- assume_invariance(a2, "spatial_translation", "h", "p")
  a2 <- test_invariance(a2, tests = "spatial_holdout", spatial_k = 3)
  expect_equal(a2$tests$spatial_holdout$verdict, "stable")
})

test_that("coords are validated and spatial_holdout needs them", {
  d <- data.frame(y = rbinom(50, 1, .5), x = rbinom(50, 1, .5), lon = runif(50))
  expect_error(structural_audit(d, outcome = "y", exposure = "x", coords = "lon"), "two column")
  a <- structural_audit(d, outcome = "y", exposure = "x")
  expect_error(test_invariance(a, tests = "spatial_holdout"), "declared coordinates")
})

test_that("E-value matches the published value and confounding_sensitivity runs", {
  expect_equal(round(evalue_from_ratio(3.9), 2), 7.26)
  expect_equal(evalue_from_ratio(1), 1)
  expect_equal(evalue_from_ratio(0.5), evalue_from_ratio(2))  # symmetric under inversion

  set.seed(4); n <- 1200
  age <- rnorm(n, 65, 9); x <- rbinom(n, 1, plogis(-0.02 * (age - 65)))
  lp <- -0.7 * x + 0.03 * (age - 65)
  te <- rexp(n, 0.05 * exp(lp)); tc <- runif(n, 1, 6)
  d <- data.frame(time = pmin(te, tc), status = as.integer(te <= tc), x = x, age = age)
  a <- structural_audit(d, outcome = c("time", "status"), exposure = "x", covariates = "age")
  a <- assume_invariance(a, "unobserved_confounding", "set may be incomplete", "adjusted HR as causal")
  a <- test_invariance(a, tests = "confounding_sensitivity", confounding_benchmark = 1.25)
  res <- a$tests$confounding_sensitivity
  expect_true(res$verdict %in% c("stable", "unstable", "not_resolvable"))
  expect_true(!is.null(res$sensitivity))
  expect_true(res$sensitivity$e_value_point >= 1)
  expect_equal(res$sensitivity$e_value_point, evalue_from_ratio(res$sensitivity$rr_point))
})

test_that("confounding_scenarios maps the tipping point and composes with the E-value", {
  expect_equal(round(bias_factor(2, 0.2, 0.2), 3), 1.167)
  mk <- function(effect, n = 12000, seed = 3) {
    set.seed(seed); age <- rnorm(n, 65, 9); x <- rbinom(n, 1, plogis(-0.02 * (age - 65)))
    lp <- effect * x + 0.03 * (age - 65); te <- rexp(n, 0.05 * exp(lp)); tc <- runif(n, 1, 6)
    d <- data.frame(time = pmin(te, tc), status = as.integer(te <= tc), x = x, age = age)
    a <- structural_audit(d, outcome = c("time", "status"), exposure = "x", covariates = "age")
    assume_invariance(a, "unobserved_confounding", "u", "c")
  }
  weak <- test_invariance(mk(-0.14), tests = "confounding_scenarios")$tests$confounding_scenarios
  expect_equal(weak$verdict, "unstable")        # a plausible confounder reaches the null
  expect_equal(length(weak$scenarios$cells), 16L)
  strong <- test_invariance(mk(-0.9, n = 4000, seed = 1), tests = "confounding_scenarios")$tests$confounding_scenarios
  expect_equal(strong$verdict, "stable")        # strong effect resists plausible confounding

  # both confounding attacks target unobserved_confounding; ledger keeps the worse verdict
  a <- test_invariance(mk(-0.14), tests = c("confounding_sensitivity", "confounding_scenarios"))
  led <- Filter(function(l) l$invariance == "unobserved_confounding", a$ledger)[[1]]
  expect_equal(led$verdict, "unstable")
})

test_that("confounding_scenarios is undefined on a linear scale", {
  d <- data.frame(y = rnorm(300), x = rbinom(300, 1, 0.5))
  a <- structural_audit(d, outcome = "y", exposure = "x")
  expect_error(test_confounding_scenarios(a), "ratio-scale")
})

test_that("confounding_sensitivity is undefined on a linear scale", {
  d <- data.frame(y = rnorm(300), x = rbinom(300, 1, 0.5))
  a <- structural_audit(d, outcome = "y", exposure = "x")
  expect_error(test_confounding_sensitivity(a), "ratio-scale")
})

test_that("graph_check detects consistent and violated DAG implications", {
  set.seed(1); n <- 1500
  a <- rnorm(n); b <- rnorm(n); cc <- a + b + rnorm(n)
  d <- data.frame(a = a, b = b, cc = cc, y = rbinom(n, 1, plogis(a)))
  au <- structural_audit(d, outcome = "y", exposure = "a")
  au <- declare_graph(au, c("a -> cc", "b -> cc", "a -> y"))
  au <- assume_invariance(au, "causal_graph", "collider DAG", "adjustment from graph")
  au <- test_invariance(au, tests = "graph_check")
  expect_equal(au$tests$graph_check$verdict, "stable")  # a,b independent -> collider parents test independent

  # correlate the two parents: a _||_ b | {} must now be violated
  set.seed(2); a2 <- rnorm(n); b2 <- 0.6 * a2 + 0.8 * rnorm(n); c2 <- a2 + b2 + rnorm(n)
  d2 <- data.frame(a = a2, b = b2, cc = c2, y = rbinom(n, 1, plogis(a2)))
  au2 <- structural_audit(d2, outcome = "y", exposure = "a")
  au2 <- declare_graph(au2, c("a -> cc", "b -> cc", "a -> y"))
  au2 <- test_invariance(au2, tests = "graph_check")
  expect_equal(au2$tests$graph_check$verdict, "unstable")
})

test_that("assumption lattice refits under pooling choices and stays schema-valid", {
  set.seed(3); n <- 1200
  h <- sample(LETTERS[1:5], n, TRUE); yr <- sample(2018:2022, n, TRUE)
  age <- rnorm(n, 65, 8); x <- rbinom(n, 1, plogis(-0.02 * (age - 65)))
  lp <- -0.6 * x + 0.03 * (age - 65); te <- rexp(n, 0.05 * exp(lp)); tc <- runif(n, 1, 6)
  d <- data.frame(time = pmin(te, tc), status = as.integer(te <= tc), x = x, age = age, h = h, yr = yr)
  a <- structural_audit(d, outcome = c("time", "status"), exposure = "x", covariates = "age",
                        cluster = "h", time = "yr")
  a <- assume_invariance(a, "cluster_exchangeability", "p", "p")
  a <- decide(test_invariance(a, tests = "cluster_holdout"))
  a <- assumption_lattice(a)
  expect_equal(length(a$lattice$nodes), 4)  # 2 axes -> 4 nodes
  expect_true(a$lattice$verdict %in% c("stable", "unstable", "not_resolvable"))
  # top node (pool both) should reproduce the main estimate
  top <- Filter(function(nd) nd$n_pooled == 2, a$lattice$nodes)[[1]]
  expect_equal(top$estimate, a$estimate$value, tolerance = 1e-6)
  hf <- tempfile(fileext = ".html"); render_report(a, hf)
  expect_true(any(grepl("assumption lattice", readLines(hf))))
})

test_that("stratified fit matches an unstratified fit when the stratum is noise", {
  set.seed(9); n <- 1500
  g <- sample(1:4, n, TRUE); x <- rbinom(n, 1, 0.5); age <- rnorm(n)
  y <- rbinom(n, 1, plogis(-0.7 * x + 0.2 * age))
  d <- data.frame(y = y, x = x, age = age, g = g)
  a <- structural_audit(d, outcome = "y", exposure = "x", covariates = "age")
  f0 <- fit_estimate(a, d)
  fs <- fit_estimate(a, d, strata = "g")
  expect_equal(sign(f0$value), sign(fs$value))  # a noise stratum does not flip the sign
})

test_that("backdoor / d-separation handles the textbook cases", {
  triangle <- list(C = character(0), X = "C", Y = c("C", "X"))
  expect_true(backdoor_valid(triangle, "X", "Y", "C"))
  expect_false(backdoor_valid(triangle, "X", "Y", character(0)))
  mediator <- list(X = character(0), M = "X", Y = "M")
  expect_true(backdoor_valid(mediator, "X", "Y", character(0)))
  # M-bias: conditioning on the collider Z opens the path
  mbias <- list(U1 = character(0), U2 = character(0), Z = c("U1", "U2"),
                X = "U1", Y = c("U2", "X"))
  expect_true(backdoor_valid(mbias, "X", "Y", character(0)))
  expect_false(backdoor_valid(mbias, "X", "Y", "Z"))
})

test_that("adjustment_check flags under- and over-adjustment against the graph", {
  set.seed(1); n <- 1000
  C <- rnorm(n); X <- rbinom(n, 1, plogis(C)); M <- X + rnorm(n)
  Y <- rbinom(n, 1, plogis(0.5 * C + 0.6 * X))
  d <- data.frame(C = C, X = X, M = M, Y = Y)
  run <- function(covs) {
    a <- structural_audit(d, outcome = "Y", exposure = "X", covariates = covs)
    a <- declare_graph(a, c("C -> X", "C -> Y", "X -> Y", "X -> M"))
    test_invariance(a, tests = "adjustment_check")$tests$adjustment_check
  }
  expect_equal(run("C")$verdict, "stable")
  expect_equal(run(character(0))$verdict, "unstable")   # open backdoor
  expect_true(run(c("C", "M"))$adjustment$over_adjustment == "M")  # mediator adjusted
  expect_equal(run(c("C", "M"))$verdict, "unstable")
})

test_that("adjustment_check reports non-identifiability under a latent confounder", {
  set.seed(1); n <- 1000
  U <- rnorm(n); C <- rnorm(n)
  X <- rbinom(n, 1, plogis(0.8 * U + 0.6 * C))
  Y <- rbinom(n, 1, plogis(0.7 * U + 0.5 * C + 0.5 * X))
  d <- data.frame(C = C, X = X, Y = Y)   # U is unmeasured
  run <- function(covs, edges, latent = character()) {
    a <- structural_audit(d, outcome = "Y", exposure = "X", covariates = covs)
    a <- declare_graph(a, edges, latent = latent)
    test_invariance(a, tests = "adjustment_check")$tests$adjustment_check
  }
  r1 <- run("C", c("U -> X", "U -> Y", "C -> X", "C -> Y", "X -> Y"), latent = "U")
  expect_equal(r1$verdict, "not_resolvable")
  expect_false(r1$adjustment$identifiable)
  r2 <- run("C", c("C -> X", "C -> Y", "X -> Y"))
  expect_equal(r2$verdict, "stable")
  expect_true(r2$adjustment$identifiable)
})

test_that("declare_graph validates latent nodes and graph_check skips latent implications", {
  d <- data.frame(C = rnorm(50), X = rbinom(50, 1, .5), Y = rbinom(50, 1, .5))
  a <- structural_audit(d, outcome = "Y", exposure = "X")
  expect_error(declare_graph(a, c("C -> X", "X -> Y"), latent = "Q"), "not in the graph")
  a <- declare_graph(a, c("U -> X", "U -> Y", "X -> Y"), latent = "U")
  gc <- test_invariance(a, tests = "graph_check")$tests$graph_check
  statuses <- vapply(gc$implications, function(im) im$status, character(1))
  expect_true(all(statuses[grepl("U", vapply(gc$implications, function(im) im$claim, character(1)))] == "not_testable"))
})

test_that("declare_graph rejects a cyclic graph and graph_check needs a declared graph", {
  d <- data.frame(a = rnorm(50), b = rnorm(50), y = rbinom(50, 1, 0.5))
  au <- structural_audit(d, outcome = "y", exposure = "a")
  expect_error(declare_graph(au, c("a -> b", "b -> a")), "acyclic")
  expect_error(test_graph_check(au), "declared graph")
})

test_that("audit export conforms to the schema shape and report renders", {
  a <- open_audit(simulate_cohort())
  a <- assume_invariance(a, "cluster_exchangeability", "same guideline", "pooling")
  a <- test_invariance(a, tests = "cluster_holdout")
  expect_error(write_audit(a, tempfile()), "decide")
  a <- decide(a)
  jf <- tempfile(fileext = ".json"); hf <- tempfile(fileext = ".html")
  write_audit(a, jf); render_report(a, hf)
  j <- jsonlite::read_json(jf)
  expect_equal(j$spec_version, "0.1")
  expect_setequal(names(j), c("spec_version", "analysis", "structure", "ledger",
                              "estimate", "tests", "decision", "provenance"))
  expect_true(j$tests[[1]]$verdict %in% c("stable", "unstable", "not_resolvable"))
  html <- readLines(hf, warn = FALSE)
  expect_true(any(grepl("invariance ledger", html)))
  expect_true(any(grepl("limitations text", html)))
})
