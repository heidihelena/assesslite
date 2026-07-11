# Worked example: does guideline adherence relate to survival, and which
# structural assumptions does that conclusion stand on?
#
# All data below are simulated. No registry or patient data appear here.

# from a source checkout, run devtools::load_all("assesslite") first
if (!isNamespaceLoaded("assesslite")) library(assesslite)

# --- simulate a multicentre cohort -------------------------------------------
set.seed(42)
n_hosp <- 12
hospitals <- sprintf("H%02d", seq_len(n_hosp))
hosp_effect <- stats::rnorm(n_hosp, 0, 0.10)          # mild between-hospital variation
n_per <- sample(120:260, n_hosp, replace = TRUE)

sim <- do.call(rbind, lapply(seq_len(n_hosp), function(h) {
  n <- n_per[h]
  age   <- round(stats::rnorm(n, 68, 9))
  sex   <- stats::rbinom(n, 1, 0.42)
  stage <- factor(sample(c("I", "II", "III", "IV"), n, replace = TRUE,
                         prob = c(0.20, 0.20, 0.30, 0.30)),
                  levels = c("I", "II", "III", "IV"))
  year  <- sample(2016:2025, n, replace = TRUE)
  # adherence is confounded by age and stage — the adjustment set matters
  p_adh <- stats::plogis(1.2 - 0.03 * (age - 68) - 0.45 * (as.integer(stage) - 1))
  adherence <- stats::rbinom(n, 1, p_adh)
  lp <- 0.03 * (age - 68) + 0.25 * sex + 0.55 * (as.integer(stage) - 1) -
        0.35 * adherence + hosp_effect[h]
  t_event  <- stats::rexp(n, rate = 0.08 * exp(lp))
  t_censor <- stats::runif(n, 1, 6)
  data.frame(hospital = hospitals[h], age = age, sex = sex, stage = stage,
             diagnosis_year = year, adherence = adherence,
             time = pmin(t_event, t_censor),
             status = as.integer(t_event <= t_censor))
}))

# --- open the audit: declare the observational world -------------------------
audit <- structural_audit(
  data       = sim,
  outcome    = c("time", "status"),
  exposure   = "adherence",
  covariates = c("age", "sex", "stage"),
  cluster    = "hospital",
  time       = "diagnosis_year",
  subgroups  = "stage",
  unit       = "patient",
  estimand   = "conditional hazard ratio for guideline adherence, adjusted for age, sex, stage"
)

# --- the invariance ledger: what is claimed, why, and what it buys -----------
audit <- assume_invariance(audit, "unit_permutation_within_cluster",
  rationale = "patient ordering within a hospital carries no causal information",
  licenses  = "pooling patients within hospital into one likelihood")

audit <- assume_invariance(audit, "cluster_exchangeability",
  rationale = "hospitals follow the same national guideline; assumed provisionally so it can be attacked",
  licenses  = "one pooled effect across hospitals; transport to a hospital outside the sample")

audit <- assume_invariance(audit, "temporal_translation",
  rationale = "no major guideline revision inside the 2016-2025 window",
  licenses  = "pooling all diagnosis years; applying the estimate forward")

audit <- assume_invariance(audit, "subgroup_transport",
  rationale = "adherence is expected to act through the same pathways at every stage",
  licenses  = "one pooled effect rather than stage-specific effects")

# --- attack the ledger --------------------------------------------------------
audit <- test_invariance(audit,
  tests = c("unit_permutation", "cluster_holdout", "temporal_split", "subgroup_stability"),
  seed = 7)

# --- decide, export, report ---------------------------------------------------
audit <- decide(audit, abstain_if = list(estimate_sign_changes = TRUE,
                                         effect_crosses_threshold = NULL))
print(audit)

out_dir <- Sys.getenv("AUDIT_OUT", unset = tempdir())
write_audit(audit, file.path(out_dir, "worked-example-audit.json"))
render_report(audit, file.path(out_dir, "worked-example-report.html"))
cat("\naudit written to ", file.path(out_dir, "worked-example-audit.json"), "\n",
    "report written to ", file.path(out_dir, "worked-example-report.html"), "\n", sep = "")
