# Decision layer (core spec v0.1, spec/abstention/rules.md).
# An abstention is a result, not a failure of the tool.

#' Apply the decision rules to a tested audit
#'
#' @param audit a structural_audit after test_invariance().
#' @param abstain_if list of user-declared abstention rules:
#'   estimate_sign_changes (logical) and effect_crosses_threshold (numeric on
#'   the natural scale, or NULL).
decide <- function(audit,
                   abstain_if = list(estimate_sign_changes = TRUE,
                                     effect_crosses_threshold = NULL)) {
  stopifnot(inherits(audit, "structural_audit"))
  e <- audit$estimate
  assumed <- Filter(function(l) l$status == "assumed", audit$ledger)
  inv_name <- function(ls) vapply(ls, function(l) l$invariance, character(1))

  load_bearing <- inv_name(Filter(function(l) isTRUE(l$tested) &&
                                    identical(l$verdict, "stable"), assumed))
  unstable_inv <- inv_name(Filter(function(l) identical(l$verdict, "unstable"), assumed))
  exposed <- inv_name(Filter(function(l) !isTRUE(l$tested) ||
                               identical(l$verdict, "not_resolvable"), assumed))

  broken_by <- NULL
  status <- NULL
  rationale <- NULL
  capped_conditional <- FALSE

  # base rule 1: resolved instability on an assumed invariance
  if (length(unstable_inv) > 0) {
    status <- "abstain"
    for (t in audit$tests) if (t$invariance %in% unstable_inv) { broken_by <- t$test; break }
    rationale <- paste0("the assumed invariance ", gsub("_", " ", unstable_inv[1]),
                        " did not hold up under the ", broken_by,
                        " attack; the pooling it licenses has no basis, so no pooled conclusion is reported")
  }

  # user rule: resolved sign change anywhere
  if (is.null(status) && isTRUE(abstain_if$estimate_sign_changes)) {
    for (t in audit$tests) {
      v <- t$variants
      if (nrow(v) == 0) next
      flip <- sign(v$estimate) != sign(e$value) & sign(e$value) != 0
      resolved <- !is.na(v$ci_low) & (v$ci_low > 0 | v$ci_high < 0)
      if (any(flip & resolved)) {
        status <- "abstain"; broken_by <- t$test
        rationale <- paste0("under the ", t$test,
                            " attack at least one variant shows a resolved sign change; ",
                            "the direction of the effect depends on a structural choice, so no direction is reported")
        break
      }
    }
  }

  # user rule: crossing a declared decision threshold
  thr <- abstain_if$effect_crosses_threshold
  if (is.null(status) && !is.null(thr)) {
    for (t in audit$tests) {
      v <- t$variants
      if (nrow(v) == 0) next
      opposite <- (e$value - thr) * (v$estimate - thr) < 0
      resolved <- !is.na(v$ci_low) & (v$ci_low > thr | v$ci_high < thr)
      if (any(opposite & resolved)) {
        status <- "abstain"; broken_by <- t$test
        rationale <- paste0("a variant under the ", t$test,
                            " attack falls on the other side of the declared threshold (",
                            format(thr), ") and its interval excludes it; the threshold verdict is not stable")
        break
      }
      if (any(opposite & !resolved)) capped_conditional <- TRUE
    }
  }

  # base rules 2 and 3
  if (is.null(status)) {
    if (length(exposed) > 0 || capped_conditional) {
      status <- "conditional"
      parts <- character(0)
      if (length(exposed) > 0)
        parts <- c(parts, paste0("the conclusion stands conditional on: ",
                                 paste(gsub("_", " ", exposed), collapse = "; "),
                                 " (untested or not resolvable at this n)"))
      if (capped_conditional)
        parts <- c(parts, paste0("at least one variant straddles the declared threshold (",
                                 format(thr),
                                 ") without resolving it; a threshold gate on an interval that includes the line cannot pass"))
      rationale <- paste(parts, collapse = "; additionally, ")
    } else {
      status <- "proceed"
      rationale <- paste0("every assumed invariance with an available attack was attacked and came back stable: ",
                          paste(gsub("_", " ", load_bearing), collapse = "; "),
                          "; within the declared structural alternatives the conclusion holds still")
    }
  }

  audit$decision <- list(status = status, rationale = rationale,
                         load_bearing = load_bearing, exposed_surface = exposed,
                         broken_by = broken_by,
                         abstention_rules = list(
                           estimate_sign_changes = isTRUE(abstain_if$estimate_sign_changes),
                           effect_crosses_threshold = thr))
  audit
}
