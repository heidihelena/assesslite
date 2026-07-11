# The invariance ledger: declared claims with rationale and licence.

add_ledger_entry <- function(audit, invariance, status, rationale, licenses) {
  stopifnot(inherits(audit, "structural_audit"))
  if (!invariance %in% invariance_vocabulary())
    stop("'", invariance, "' is not in the core invariance vocabulary; see ",
         "spec/schema/invariance-vocabulary.md. Known: ",
         paste(invariance_vocabulary(), collapse = ", "))
  if (missing(rationale) || !nzchar(rationale))
    stop("a rationale is required: why is this claim scientifically ",
         if (status == "assumed") "defensible" else "indefensible", " here?")
  if (missing(licenses) || !nzchar(licenses))
    stop("a licence is required: what inferential step does this claim ",
         if (status == "assumed") "buy" else "remove from scope", "?")
  existing <- vapply(audit$ledger, function(l) l$invariance, character(1))
  if (invariance %in% existing)
    stop("'", invariance, "' is already in the ledger; one entry per claim")
  audit$ledger[[length(audit$ledger) + 1]] <- list(
    invariance = invariance, status = status,
    rationale = rationale, licenses = licenses,
    tested = FALSE, verdict = NULL)
  audit
}

#' Assume an invariance: the analysis relies on it and it should be attacked
assume_invariance <- function(audit, invariance, rationale, licenses) {
  add_ledger_entry(audit, invariance, "assumed", rationale, licenses)
}

#' Reject an invariance: the analyst asserts it does not hold here
reject_invariance <- function(audit, invariance, rationale, licenses) {
  add_ledger_entry(audit, invariance, "rejected", rationale, licenses)
}

ledger_status <- function(audit, invariance) {
  for (l in audit$ledger) if (l$invariance == invariance) return(l$status)
  NA_character_
}

# Record a verdict on a ledger invariance. When more than one attack targets the
# same invariance, the ledger keeps the worst verdict (an invariance is only as solid
# as its weakest attack): unstable > not_resolvable > stable.
mark_tested <- function(audit, invariance, verdict) {
  rank <- c(stable = 0L, not_resolvable = 1L, unstable = 2L)
  for (i in seq_along(audit$ledger)) {
    if (audit$ledger[[i]]$invariance == invariance) {
      old <- audit$ledger[[i]]$verdict
      combined <- if (isTRUE(audit$ledger[[i]]$tested) && !is.null(old) &&
                      rank[[old]] > rank[[verdict]]) old else verdict
      audit$ledger[[i]]$tested <- TRUE
      audit$ledger[[i]]$verdict <- combined
    }
  }
  audit
}
