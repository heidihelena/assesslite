import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from assesslite import StructuralAudit
from assesslite.core import invariance_vocabulary
from assesslite.stability import stability_metrics, verdict_from_metrics

SCHEMA = Path(__file__).resolve().parents[2] / "spec" / "schema" / "audit.schema.json"


def simulate_cohort(n=600, effect=-0.4, seed=1):
    rng = np.random.default_rng(seed)
    hospital = rng.choice([f"H{i}" for i in range(1, 7)], n)
    year = rng.integers(2018, 2024, n)
    age = rng.normal(65, 8, n)
    x = rng.binomial(1, 1 / (1 + np.exp(0.02 * (age - 65))))
    y = rng.binomial(1, 1 / (1 + np.exp(-(-1 + 0.04 * (age - 65) + effect * x))))
    return pd.DataFrame({"hospital": hospital, "year": year, "age": age, "x": x, "y": y})


def open_audit(d):
    return StructuralAudit(d, outcome="y", exposure="x", covariates=["age"],
                           cluster="hospital", time="year", unit="patient")


def test_constructor_detects_binomial_and_fits():
    a = open_audit(simulate_cohort(n=1500, effect=-1.0))
    assert a.analysis["estimator"] == "glm_binomial"
    assert np.isfinite(a.estimate["value"])
    assert a.estimate["value"] < 0


def test_ledger_enforces_vocabulary_and_requires_rationale_and_licence():
    a = open_audit(simulate_cohort())
    with pytest.raises(ValueError, match="vocabulary"):
        a.assume("my_new_symmetry", "r", "l")
    with pytest.raises(ValueError, match="rationale"):
        a.assume("cluster_exchangeability", "", "l")
    with pytest.raises(ValueError, match="licence"):
        a.assume("cluster_exchangeability", "r", "")
    a.assume("cluster_exchangeability", "same guideline", "pooling")
    with pytest.raises(ValueError, match="already in the ledger"):
        a.assume("cluster_exchangeability", "again", "again")


def test_verdict_rule_is_three_way():
    v = pd.DataFrame([{"label": "a", "estimate": 0.5, "se": 0.1, "ci_low": 0.3, "ci_high": 0.7, "n": 100}])
    assert verdict_from_metrics(stability_metrics(0.5, 0.1, 0.3, 0.7, v), 0.5, 0.1) == "stable"
    v2 = pd.DataFrame([{"label": "a", "estimate": -0.5, "se": 0.1, "ci_low": -0.7, "ci_high": -0.3, "n": 100}])
    assert verdict_from_metrics(stability_metrics(0.5, 0.1, 0.3, 0.7, v2), 0.5, 0.1) == "unstable"
    v3 = pd.DataFrame([{"label": "a", "estimate": 0.5, "se": 2.0, "ci_low": -3.4, "ci_high": 4.4, "n": 20}])
    assert verdict_from_metrics(stability_metrics(0.5, 0.1, 0.3, 0.7, v3), 0.5, 0.1) == "not_resolvable"


def test_unit_permutation_is_stable():
    a = open_audit(simulate_cohort())
    a.assume("unit_permutation_within_cluster", "ordering carries no information", "pooling within cluster")
    a.test(["unit_permutation"], seed=3)
    assert a.tests["unit_permutation"]["verdict"] == "stable"


def test_rejected_invariance_not_tested():
    a = open_audit(simulate_cohort())
    a.reject("cluster_exchangeability", "hospitals differ by design", "cluster enters as structure")
    with pytest.warns(UserWarning, match="rejected"):
        a.test(["cluster_holdout"])
    assert len(a.tests) == 0


def test_decision_abstains_on_resolved_instability():
    d = simulate_cohort(n=2000, effect=-0.6, seed=2)
    flip = d["hospital"] == "H1"
    rng = np.random.default_rng(5)
    d.loc[flip, "y"] = rng.binomial(1, 1 / (1 + np.exp(-(-1 + 2.5 * d.loc[flip, "x"]))))
    a = open_audit(d)
    a.assume("cluster_exchangeability", "assumed provisionally", "pooling")
    a.test(["cluster_holdout"])
    a.decide()
    assert a.decision["status"] == "abstain"
    assert a.decision["broken_by"] == "cluster_holdout"


def test_untested_assumed_caps_at_conditional():
    a = open_audit(simulate_cohort())
    a.assume("temporal_translation", "no revisions in window", "pooling years")
    a.assume("cluster_exchangeability", "same guideline", "pooling clusters")
    a.test(["cluster_holdout"])
    a.decide()
    assert a.decision["status"] in ("conditional", "abstain")
    if a.decision["status"] == "conditional":
        assert "temporal_translation" in a.decision["exposed_surface"]


def test_export_conforms_to_schema_and_report_renders(tmp_path):
    import jsonschema

    a = open_audit(simulate_cohort())
    a.assume("cluster_exchangeability", "same guideline", "pooling")
    a.test(["cluster_holdout"])
    with pytest.raises(RuntimeError, match="decide"):
        a.export_audit()
    a.decide()
    jf = tmp_path / "audit.json"
    hf = tmp_path / "report.html"
    audit = a.export_audit(str(jf))
    a.render_report(str(hf))

    schema = json.loads(SCHEMA.read_text())
    jsonschema.validate(instance=audit, schema=schema)  # round-trip contract: same schema as R

    assert audit["spec_version"] == "0.1"
    assert set(audit) == {"spec_version", "analysis", "structure", "ledger",
                          "estimate", "tests", "decision", "provenance"}
    assert audit["tests"][0]["verdict"] in ("stable", "unstable", "not_resolvable")
    html = hf.read_text()
    assert "invariance ledger" in html
    assert "limitations text" in html


def test_vocabulary_matches_spec():
    assert "unit_permutation" in invariance_vocabulary()
    assert "spatial_translation" in invariance_vocabulary()
    assert "unobserved_confounding" in invariance_vocabulary()


def simulate_survival(n=1200, effect=-0.7, seed=4):
    rng = np.random.default_rng(seed)
    age = rng.normal(65, 9, n)
    x = rng.binomial(1, 1 / (1 + np.exp(0.02 * (age - 65))))
    lp = effect * x + 0.03 * (age - 65)
    te = rng.exponential(1 / (0.05 * np.exp(lp)))
    tc = rng.uniform(1, 6, n)
    return pd.DataFrame({"time": np.minimum(te, tc), "status": (te <= tc).astype(int),
                         "x": x, "age": age})


def test_evalue_matches_published_and_confounding_sensitivity_runs():
    from assesslite.sensitivity import evalue_from_ratio
    assert round(evalue_from_ratio(3.9), 2) == 7.26
    assert evalue_from_ratio(1) == 1
    assert evalue_from_ratio(0.5) == evalue_from_ratio(2)  # symmetric under inversion

    a = StructuralAudit(simulate_survival(), outcome=("time", "status"),
                        exposure="x", covariates=["age"])
    a.assume("unobserved_confounding", "set may be incomplete", "adjusted HR as causal")
    a.test(["confounding_sensitivity"], confounding_benchmark=1.25)
    res = a.tests["confounding_sensitivity"]
    assert res["verdict"] in ("stable", "unstable", "not_resolvable")
    assert res["sensitivity"] is not None
    assert res["sensitivity"]["e_value_point"] >= 1
    assert abs(res["sensitivity"]["e_value_point"]
               - evalue_from_ratio(res["sensitivity"]["rr_point"])) < 1e-9


def test_confounding_sensitivity_undefined_on_linear_scale():
    d = pd.DataFrame({"y": np.random.default_rng(0).normal(0, 1, 300),
                      "x": np.random.default_rng(1).binomial(1, 0.5, 300)})
    a = StructuralAudit(d, outcome="y", exposure="x")
    with pytest.raises(ValueError, match="ratio-scale"):
        a.test(["confounding_sensitivity"])


def test_sensitivity_audit_conforms_to_schema(tmp_path):
    import jsonschema
    a = StructuralAudit(simulate_survival(), outcome=("time", "status"),
                        exposure="x", covariates=["age"])
    a.assume("unobserved_confounding", "set may be incomplete", "adjusted HR as causal")
    a.test(["confounding_sensitivity"]).decide()
    audit = a.export_audit()
    schema = json.loads(SCHEMA.read_text())
    jsonschema.validate(audit, schema)
    hf = tmp_path / "r.html"
    a.render_report(str(hf))
    assert "E-value" in hf.read_text()
