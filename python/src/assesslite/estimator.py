"""Estimator detection and fitting (AssessLite core spec v0.1).

Mirrors the R engine's fit_estimate(): fits the declared estimator on a data
subset and returns the exposure coefficient on its natural scale, or None if the
fit fails. Estimators are implemented in pure numpy to keep the package portable:
GLM by iteratively reweighted least squares, Cox by Breslow partial-likelihood
Newton-Raphson. No compiled or version-fragile stats dependency.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

SPEC_VERSION = "0.1"


def _is_binary(y: pd.Series) -> bool:
    if not pd.api.types.is_numeric_dtype(y):
        return False
    return set(pd.unique(y.dropna())).issubset({0, 1})


def detect_estimator(data: pd.DataFrame, outcome) -> tuple[str, str]:
    """Return (estimator, scale) from the outcome specification."""
    if isinstance(outcome, (list, tuple)) and len(outcome) == 2:
        return "coxph", "log hazard ratio"
    if isinstance(outcome, (list, tuple)):
        raise ValueError("outcome must be one column name or (time, status)")
    y = data[outcome]
    if _is_binary(y):
        return "glm_binomial", "log odds ratio"
    if pd.api.types.is_numeric_dtype(y):
        return "glm_gaussian", "linear coefficient"
    raise ValueError("outcome must be numeric (binary 0/1 or continuous), or (time, status)")


def _design_matrix(data: pd.DataFrame, exposure: str, covariates, intercept: bool):
    """Build a design matrix; expand non-numeric covariates as drop-first dummies."""
    blocks, names = [], []

    def add(col):
        s = data[col]
        is_factor = isinstance(s.dtype, pd.CategoricalDtype) or not pd.api.types.is_numeric_dtype(s)
        if is_factor:
            dummies = pd.get_dummies(s, prefix=col, prefix_sep="=", drop_first=True)
            if dummies.shape[1] == 0:
                return
            blocks.append(dummies.to_numpy(dtype=float))
            names.extend(list(dummies.columns))
        else:
            blocks.append(s.to_numpy(dtype=float).reshape(-1, 1))
            names.append(col)

    add(exposure)
    for c in covariates:
        add(c)
    X = np.hstack(blocks) if blocks else np.empty((len(data), 0))
    if intercept:
        X = np.hstack([np.ones((len(data), 1)), X])
        names = ["(Intercept)"] + names
    return X, names


def _fit_glm(X, y, family, max_iter=50, tol=1e-8):
    n, p = X.shape
    beta = np.zeros(p)
    if family == "glm_gaussian":
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        dof = max(n - p, 1)
        sigma2 = float(resid @ resid) / dof
        cov = sigma2 * np.linalg.inv(X.T @ X)
        return beta, np.sqrt(np.diag(cov))
    # binomial logit via IRLS
    for _ in range(max_iter):
        eta = X @ beta
        eta = np.clip(eta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1.0 - mu), 1e-9, None)
        z = eta + (y - mu) / w
        WX = X * w[:, None]
        xtwx = X.T @ WX
        xtwz = X.T @ (w * z)
        beta_new = np.linalg.solve(xtwx, xtwz)
        if not np.all(np.isfinite(beta_new)):
            raise np.linalg.LinAlgError("non-finite GLM update")
        if np.max(np.abs(beta_new - beta)) < tol:
            beta = beta_new
            break
        beta = beta_new
    eta = np.clip(X @ beta, -30, 30)
    mu = 1.0 / (1.0 + np.exp(-eta))
    w = np.clip(mu * (1.0 - mu), 1e-9, None)
    cov = np.linalg.inv(X.T @ (X * w[:, None]))
    return beta, np.sqrt(np.diag(cov))


def _cox_grad_hess(X, time, status, beta):
    """Breslow partial-likelihood gradient and Hessian for one stratum."""
    n, p = X.shape
    order = np.argsort(-time, kind="mergesort")  # descending time
    Xo, to, so = X[order], time[order], status[order]
    theta = np.exp(np.clip(Xo @ beta, -30, 30))
    grad = np.zeros(p)
    hess = np.zeros((p, p))
    S0 = 0.0
    S1 = np.zeros(p)
    S2 = np.zeros((p, p))
    i = 0
    while i < n:
        j = i
        # accumulate all rows tied at this time into the risk set first
        while j < n and to[j] == to[i]:
            xj = Xo[j]
            tj = theta[j]
            S0 += tj
            S1 += tj * xj
            S2 += tj * np.outer(xj, xj)
            j += 1
        d = int(so[i:j].sum())
        if d > 0:
            mean = S1 / S0
            grad += Xo[i:j][so[i:j] == 1].sum(axis=0) - d * mean
            hess -= d * (S2 / S0 - np.outer(mean, mean))
        i = j
    return grad, hess


def _fit_cox(X, time, status, strata=None, max_iter=50, tol=1e-8):
    """Cox partial likelihood (Breslow ties), Newton-Raphson. `strata` gives
    separate baseline hazards: risk sets are accumulated within each stratum."""
    n, p = X.shape
    if strata is None:
        groups = [np.arange(n)]
    else:
        groups = [np.where(strata == s)[0] for s in pd.unique(strata)]
    beta = np.zeros(p)
    for _ in range(max_iter):
        grad = np.zeros(p)
        hess = np.zeros((p, p))
        for g in groups:
            gg, hh = _cox_grad_hess(X[g], time[g], status[g], beta)
            grad += gg
            hess += hh
        step = np.linalg.solve(-hess, grad)
        beta_new = beta + step
        if not np.all(np.isfinite(beta_new)):
            raise np.linalg.LinAlgError("non-finite Cox update")
        if np.max(np.abs(step)) < tol:
            beta = beta_new
            break
        beta = beta_new
    hess = np.zeros((p, p))
    for g in groups:
        _, hh = _cox_grad_hess(X[g], time[g], status[g], beta)
        hess += hh
    cov = np.linalg.inv(-hess)
    return beta, np.sqrt(np.diag(cov))


def fit_estimate(analysis: dict, data: pd.DataFrame, strata=()) -> Optional[dict]:
    """Fit the declared estimator; return dict(value, se, ci_low, ci_high, n) or None.

    `strata` names variables to condition on without pooling: Cox strata (separate
    baseline hazards) or GLM fixed-effect factors. Used by the assumption lattice.
    """
    exposure = analysis["exposure"]
    covariates = list(analysis["covariates"])
    outcome_cols = analysis["outcome_cols"]
    estimator = analysis["estimator"]
    strata = [s for s in strata if s not in [exposure] + covariates]

    used = list(outcome_cols) + [exposure] + covariates + list(strata)
    cc = data[used].dropna()
    n = int(cc.shape[0])
    if n < len(used) + 2:
        return None

    try:
        if estimator == "coxph":
            X, names = _design_matrix(cc, exposure, covariates, intercept=False)
            time = cc[outcome_cols[0]].to_numpy(dtype=float)
            status = cc[outcome_cols[1]].to_numpy(dtype=float)
            strat = None
            if strata:
                strat = cc[strata].astype(str).agg("|".join, axis=1).to_numpy()
            beta, se = _fit_cox(X, time, status, strata=strat)
        else:
            gcov = covariates + list(strata)
            cc2 = cc.copy()
            for s in strata:
                cc2[s] = cc2[s].astype("category")
            X, names = _design_matrix(cc2, exposure, gcov, intercept=True)
            y = cc2[outcome_cols[0]].to_numpy(dtype=float)
            beta, se = _fit_glm(X, y, estimator)
    except (np.linalg.LinAlgError, ValueError, FloatingPointError):
        return None

    idx = [k for k, nm in enumerate(names) if str(nm).startswith(exposure)]
    if not idx:
        return None
    k = idx[0]
    est, s = float(beta[k]), float(se[k])
    if not (np.isfinite(est) and np.isfinite(s)):
        return None
    return {"value": est, "se": s, "ci_low": est - 1.96 * s, "ci_high": est + 1.96 * s, "n": n}
