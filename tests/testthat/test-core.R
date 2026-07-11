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

test_that("confounding_sensitivity is undefined on a linear scale", {
  d <- data.frame(y = rnorm(300), x = rbinom(300, 1, 0.5))
  a <- structural_audit(d, outcome = "y", exposure = "x")
  expect_error(test_confounding_sensitivity(a), "ratio-scale")
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
