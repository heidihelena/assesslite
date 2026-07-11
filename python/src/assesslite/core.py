"""AssessLite core: the StructuralAudit object (the assessment) and its ledger.

AssessLite is the product, StructuralAudit(...) opens an assessment, and
export_audit() writes the durable audit record. R implementation of the same spec
lives in ../R; this is the native Python interface. Conceptual objects are identical
across the two; the APIs feel native to each language.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import autocorrelation as _autocorr
from . import decision as _decision
from . import export as _export
from . import graph as _graph
from . import lattice as _lattice
from . import network as _network
from . import positivity as _positivity
from . import report as _report
from . import scenarios as _scenarios
from . import sensitivity as _sens
from . import spatial as _spatial
from . import transformations as _tf
from .estimator import detect_estimator, fit_estimate

INVARIANCE_VOCABULARY = (
    "unit_permutation",
    "unit_permutation_within_cluster",
    "cluster_exchangeability",
    "temporal_translation",
    "subgroup_transport",
    "unobserved_confounding",
    "causal_graph",
    "adjustment_sufficiency",
    "positivity",
    "spatial_translation",
    "spatial_independence",
    "network_relabelling",
)

_DEFAULT_TESTS = ("unit_permutation", "cluster_holdout", "temporal_split", "subgroup_stability")
_KNOWN_TESTS = _DEFAULT_TESTS + ("confounding_sensitivity", "graph_check", "adjustment_check",
                                 "spatial_holdout", "interference_check", "positivity_check",
                                 "confounding_scenarios", "spatial_autocorrelation")


def invariance_vocabulary() -> tuple:
    """Canonical invariance identifiers (core spec v0.1)."""
    return INVARIANCE_VOCABULARY


class StructuralAudit:
    """An assessment: declare structure, build the invariance ledger, attack it, decide.

    Example
    -------
    >>> a = StructuralAudit(df, outcome=("time", "status"), exposure="adherence",
    ...                     covariates=["age", "sex", "stage"], cluster="hospital",
    ...                     time="diagnosis_year", subgroups=["stage"])
    >>> a.assume("cluster_exchangeability", rationale="...", licenses="...")
    >>> a.test().decide(abstain_if={"estimate_sign_changes": True})
    >>> audit = a.export_audit("audit.json")
    >>> a.render_report("report.html")
    """

    def __init__(self, data: pd.DataFrame, outcome, exposure: str,
                 covariates=None, cluster: str | None = None, time: str | None = None,
                 subgroups=None, coords=None, unit_id: str | None = None, edges=None,
                 unit: str = "unit", estimand: str | None = None):
        if not isinstance(data, pd.DataFrame):
            raise TypeError("data must be a pandas DataFrame")
        # a bare string is one name, not an iterable of characters
        covariates = [covariates] if isinstance(covariates, str) else list(covariates or [])
        subgroups = [subgroups] if isinstance(subgroups, str) else list(subgroups or [])
        if coords is not None:
            if isinstance(coords, str):
                raise ValueError("coords must be two column names, (x, y) or (lon, lat)")
            coords = list(coords)
            if len(coords) != 2:
                raise ValueError("coords must be two column names, (x, y) or (lon, lat)")
        outcome_cols = list(outcome) if isinstance(outcome, (list, tuple)) else [outcome]

        needed = outcome_cols + [exposure] + covariates + \
            ([cluster] if cluster else []) + ([time] if time else []) + subgroups + \
            (list(coords) if coords else []) + ([unit_id] if unit_id else [])
        missing = [c for c in needed if c not in data.columns]
        if missing:
            raise ValueError("columns not in data: " + ", ".join(missing))
        if coords is not None and not all(pd.api.types.is_numeric_dtype(data[c]) for c in coords):
            raise ValueError("coords columns must be numeric")

        network = None
        if edges is not None:
            if unit_id is None:
                raise ValueError("edges require a unit_id column naming each unit")
            edges = pd.DataFrame(edges).iloc[:, :2]
            if edges.shape[1] < 2:
                raise ValueError("edges must have two columns of unit ids (undirected)")
            if data[unit_id].astype(str).duplicated().any():
                raise ValueError("unit_id values must be unique (one row per unit)")
            network = {"unit_id": unit_id, "edges": edges, "n_edges": int(edges.shape[0])}

        estimator, scale = detect_estimator(data, outcome)
        if estimand is None:
            estimand = f"effect of {exposure} on {'/'.join(outcome_cols)} ({scale})"

        self.data = data.reset_index(drop=True)
        self.analysis = {
            "unit": unit, "outcome": "/".join(outcome_cols), "outcome_cols": outcome_cols,
            "exposure": exposure, "covariates": covariates, "estimand": estimand,
            "estimator": estimator, "scale": scale,
        }
        self.structure = {"cluster": cluster, "time": time, "subgroups": subgroups,
                          "coords": coords, "unit_id": unit_id,
                          "n_edges": network["n_edges"] if network else None}
        self.network = network
        self.ledger: list[dict] = []
        self.tests: dict[str, dict] = {}
        self.decision: dict | None = None
        self.graph: dict | None = None
        self.lattice: dict | None = None

        self.estimate = fit_estimate(self.analysis, self.data)
        if self.estimate is None:
            raise RuntimeError("the full-sample model could not be fitted; assessment not opened")

    # --- ledger ---------------------------------------------------------------
    def _add(self, invariance, status, rationale, licenses):
        if invariance not in INVARIANCE_VOCABULARY:
            raise ValueError(
                f"'{invariance}' is not in the core invariance vocabulary; see "
                f"spec/schema/invariance-vocabulary.md. Known: {', '.join(INVARIANCE_VOCABULARY)}")
        if not rationale:
            raise ValueError("a rationale is required: why is this claim scientifically "
                             + ("defensible" if status == "assumed" else "indefensible") + " here?")
        if not licenses:
            raise ValueError("a licence is required: what inferential step does this claim "
                             + ("buy" if status == "assumed" else "remove from scope") + "?")
        if any(l["invariance"] == invariance for l in self.ledger):
            raise ValueError(f"'{invariance}' is already in the ledger; one entry per claim")
        self.ledger.append({"invariance": invariance, "status": status, "rationale": rationale,
                            "licenses": licenses, "tested": False, "verdict": None})
        return self

    def declare_graph(self, edges, latent=()):
        """Declare a causal DAG (edges like 'age -> adherence') for the graph checks.

        latent names nodes that are part of the causal structure but not measured
        (e.g. an unmeasured confounder); they may not enter an adjustment set, and
        implications that touch them are not testable.
        """
        g = _graph.parse_graph(edges)
        latent = list(latent)
        bad = [v for v in latent if v not in g["nodes"]]
        if bad:
            raise ValueError("latent nodes not in the graph: " + ", ".join(bad))
        g["latent"] = latent
        missing = [v for v in g["nodes"] if v not in latent and v not in self.data.columns]
        if missing:
            import warnings
            warnings.warn("graph nodes not found in the data and not declared latent "
                          "(implications involving them will be skipped): " + ", ".join(missing))
        self.graph = g
        return self

    def assume(self, invariance, rationale, licenses):
        """Assume an invariance: the analysis relies on it and it should be attacked."""
        return self._add(invariance, "assumed", rationale, licenses)

    def reject(self, invariance, rationale, licenses):
        """Reject an invariance: the analyst asserts it does not hold here."""
        return self._add(invariance, "rejected", rationale, licenses)

    def _ledger_status(self, invariance):
        for l in self.ledger:
            if l["invariance"] == invariance:
                return l["status"]
        return None

    def _mark_tested(self, invariance, verdict):
        # when more than one attack targets an invariance, keep the worst verdict
        # (unstable > not_resolvable > stable)
        rank = {"stable": 0, "not_resolvable": 1, "unstable": 2}
        for l in self.ledger:
            if l["invariance"] == invariance:
                if l["tested"] and l["verdict"] is not None and rank[l["verdict"]] > rank[verdict]:
                    pass  # keep the existing (worse) verdict
                else:
                    l["verdict"] = verdict
                l["tested"] = True

    # --- attacks --------------------------------------------------------------
    def test(self, tests=_DEFAULT_TESTS, seed: int = 1, confounding_benchmark: float = 1.25,
             outcome_node=None, spatial_k: int = 3, tip_ratio=None,
             confounder_prevalence: float = 0.2, spatial_knn: int = 8):
        """Run attacks against the declared invariances.

        tests may include confounding_sensitivity (E-value) and graph_check /
        adjustment_check (which need a graph declared via declare_graph).
        outcome_node names the graph node to treat as the outcome for
        adjustment_check (defaults to the model's outcome column).
        """
        bad = [t for t in tests if t not in _KNOWN_TESTS]
        if bad:
            raise ValueError("unknown tests: " + ", ".join(bad))
        rng = np.random.default_rng(seed)
        runners = {
            "unit_permutation": lambda: _tf.test_unit_permutation(self, rng),
            "cluster_holdout": lambda: _tf.test_cluster_holdout(self),
            "temporal_split": lambda: _tf.test_temporal_split(self),
            "subgroup_stability": lambda: _tf.test_subgroup_stability(self),
            "confounding_sensitivity": lambda: _sens.test_confounding_sensitivity(self, confounding_benchmark),
            "graph_check": lambda: _graph.test_graph_check(self),
            "adjustment_check": lambda: _graph.test_adjustment_check(self, outcome_node),
            "spatial_holdout": lambda: _spatial.test_spatial_holdout(self, spatial_k),
            "interference_check": lambda: _network.test_interference(self),
            "positivity_check": lambda: _positivity.test_positivity(self),
            "confounding_scenarios": lambda: _scenarios.test_confounding_scenarios(
                self, confounder_prevalence, tip_ratio),
            "spatial_autocorrelation": lambda: _autocorr.test_spatial_autocorrelation(self, spatial_knn),
        }
        for t in tests:
            inv = _tf.target_invariance(self, t)
            if self._ledger_status(inv) == "rejected":
                import warnings
                warnings.warn(f"skipping {t}: {inv} is rejected in the ledger and is not tested "
                              "against (core spec, abstention rules)")
                continue
            res = runners[t]()
            self.tests[t] = res
            self._mark_tested(res["invariance"], res["verdict"])
        return self

    # --- decision, export, report --------------------------------------------
    def decide(self, abstain_if: dict | None = None):
        self.decision = _decision.decide(self, abstain_if)
        return self

    def assumption_lattice(self):
        """Refit the exposure estimate under every pool-or-stratify choice over the
        declared cluster/time axes; store the resulting lattice on the assessment."""
        self.lattice = _lattice.build_lattice(self)
        return self

    def export_audit(self, path: str | None = None) -> dict:
        return _export.export_audit(self, path)

    def render_report(self, path: str) -> str:
        return _report.render_report(self, path)

    def __repr__(self):
        e = self.estimate
        lines = [f"StructuralAudit (AssessLite, core spec 0.1)",
                 f"  estimand : {self.analysis['estimand']}",
                 f"  estimator: {self.analysis['estimator']} on {self.analysis['scale']}",
                 f"  estimate : {e['value']:.3f} [{e['ci_low']:.3f}, {e['ci_high']:.3f}], n = {e['n']}"]
        if self.ledger:
            lines.append("  ledger   :")
            for l in self.ledger:
                if l["tested"]:
                    v = " -> " + l["verdict"].replace("_", " ")
                elif l["status"] == "assumed":
                    v = " (untested)"
                else:
                    v = ""
                lines.append(f"    [{l['status']}] {l['invariance']}{v}")
        if self.tests:
            lines.append("  attacks  :")
            for t in self.tests.values():
                lines.append(f"    {t['test']} -> {t['verdict'].replace('_', ' ')}")
        if self.decision:
            lines.append(f"  decision : {self.decision['status'].upper()} - {self.decision['rationale']}")
        return "\n".join(lines)
