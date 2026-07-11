# Audit export: the complete reasoning path as one JSON object conforming to
# spec/schema/audit.schema.json.

audit_as_list <- function(audit) {
  stopifnot(inherits(audit, "structural_audit"))
  if (is.null(audit$decision))
    stop("run decide() before exporting; an audit without a decision is not complete")

  tf <- tempfile(); on.exit(unlink(tf), add = TRUE)
  saveRDS(audit$data, tf)
  fingerprint <- list(n_rows = nrow(audit$data), n_cols = ncol(audit$data),
                      md5 = unname(tools::md5sum(tf)))

  tests <- unname(lapply(audit$tests, function(t) {
    v <- t$variants
    obj <- list(test = t$test, invariance = t$invariance, verdict = t$verdict,
                variants = lapply(seq_len(nrow(v)), function(i) as.list(v[i, ])),
                n_failed_refits = t$n_failed,
                reading = t$reading)
    if (!is.null(t$metrics)) obj$metrics <- t$metrics
    if (!is.null(t$sensitivity)) obj$sensitivity <- t$sensitivity
    if (!is.null(t$implications)) obj$implications <- lapply(t$implications, function(im) {
      im$conditioning <- I(as.character(im$conditioning)); im
    })
    if (!is.null(t$adjustment)) obj$adjustment <- t$adjustment
    obj
  }))

  # wrap array-typed fields so jsonlite's auto_unbox does not collapse a
  # single-element vector to a scalar (which would break the schema's array types
  # and diverge from the Python export)
  analysis <- audit$analysis[c("unit", "outcome", "exposure", "covariates",
                               "estimand", "estimator", "scale")]
  analysis$covariates <- I(as.character(analysis$covariates))
  structure <- audit$structure
  structure$subgroups <- I(as.character(structure$subgroups))
  decision <- audit$decision
  decision$load_bearing <- I(as.character(decision$load_bearing))
  decision$exposed_surface <- I(as.character(decision$exposed_surface))

  out <- list(
    spec_version = "0.1",
    analysis = analysis,
    structure = structure,
    ledger = lapply(audit$ledger, function(l)
      list(invariance = l$invariance, status = l$status, rationale = l$rationale,
           licenses = l$licenses, tested = l$tested, verdict = l$verdict)),
    estimate = audit$estimate,
    tests = tests,
    decision = decision,
    provenance = list(
      created = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
      engine = "assesslite",
      engine_version = tryCatch(as.character(utils::packageVersion("assesslite")),
                                error = function(e) "0.1.0"),
      platform = R.version.string,
      spec_version = "0.1",
      data_fingerprint = fingerprint)
  )
  if (!is.null(audit$lattice)) out$lattice <- audit$lattice
  out
}

#' Write the audit to a JSON file conforming to the core audit schema
write_audit <- function(audit, path) {
  jsonlite::write_json(audit_as_list(audit), path,
                       auto_unbox = TRUE, pretty = TRUE, digits = 10,
                       null = "null", na = "null")
  invisible(path)
}
