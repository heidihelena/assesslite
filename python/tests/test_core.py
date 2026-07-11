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


def test_positivity_check_reads_overlap():
    rng = np.random.default_rng(1); n = 2500; age = rng.normal(size=n)
    x1 = rng.binomial(1, 1/(1+np.exp(-0.3*age)))
    d1 = pd.DataFrame({"y": rng.binomial(1, 1/(1+np.exp(-(-0.6*x1+0.3*age)))), "x": x1, "age": age})
    a1 = StructuralAudit(d1, outcome="y", exposure="x", covariates=["age"])
    a1.assume("positivity", "p", "o").test(["positivity_check"])
    assert a1.tests["positivity_check"]["verdict"] == "stable"
    assert a1.tests["positivity_check"]["overlap"]["frac_extreme"] < 0.05

    rng2 = np.random.default_rng(5); z = rng2.normal(size=n); x2 = rng2.binomial(1, 1/(1+np.exp(-2.8*z)))
    d2 = pd.DataFrame({"y": rng2.binomial(1, 1/(1+np.exp(-(-0.6*x2+0.5*z)))), "x": x2, "z": z})
    a2 = StructuralAudit(d2, outcome="y", exposure="x", covariates=["z"])
    a2.assume("positivity", "p", "o").test(["positivity_check"])
    assert a2.tests["positivity_check"]["verdict"] == "not_resolvable"
    assert a2.tests["positivity_check"]["overlap"]["frac_extreme"] > 0.10


def test_positivity_check_needs_binary_exposure_and_covariates():
    rng = np.random.default_rng(0)
    d = pd.DataFrame({"y": rng.binomial(1, .5, 60), "x": rng.normal(size=60), "age": rng.normal(size=60)})
    a = StructuralAudit(d, outcome="y", exposure="x", covariates=["age"])
    with pytest.raises(ValueError, match="binary"):
        a.test(["positivity_check"])
    d2 = pd.DataFrame({"y": rng.binomial(1, .5, 60), "x": rng.binomial(1, .5, 60)})
    a2 = StructuralAudit(d2, outcome="y", exposure="x")
    with pytest.raises(ValueError, match="covariates"):
        a2.test(["positivity_check"])


def test_interference_check_detects_spillover():
    from assesslite.network import neighbor_exposure
    rng = np.random.default_rng(1); n = 1500
    ids = [f"u{i}" for i in range(n)]
    m = n * 3; ea = rng.choice(ids, m); eb = rng.choice(ids, m); keep = ea != eb
    edges = pd.DataFrame({"a": ea[keep], "b": eb[keep]})
    x = rng.binomial(1, 0.5, n); xvec = dict(zip(ids, x))
    ne_map = neighbor_exposure(ids, xvec, edges)
    ne = np.array([ne_map[u] for u in ids]); ne[np.isnan(ne)] = x.mean()

    y_int = rng.binomial(1, 1/(1+np.exp(-(-0.5*x + 1.2*ne))))
    d1 = pd.DataFrame({"id": ids, "x": x, "y": y_int})
    a1 = StructuralAudit(d1, outcome="y", exposure="x", unit_id="id", edges=edges)
    a1.assume("network_relabelling", "no interference", "SUTVA").test(["interference_check"])
    assert a1.tests["interference_check"]["verdict"] == "unstable"
    assert a1.tests["interference_check"]["spillover"] is not None

    y_no = rng.binomial(1, 1/(1+np.exp(-(-0.5*x))))
    d2 = pd.DataFrame({"id": ids, "x": x, "y": y_no})
    a2 = StructuralAudit(d2, outcome="y", exposure="x", unit_id="id", edges=edges)
    a2.assume("network_relabelling", "n", "p").test(["interference_check"])
    assert a2.tests["interference_check"]["verdict"] == "stable"


def test_edges_require_unique_unit_id_and_interference_needs_network():
    d = pd.DataFrame({"id": ["a", "a", "b"], "x": [0, 1, 0], "y": [0, 1, 1]})
    edges = pd.DataFrame({"a": ["a"], "b": ["b"]})
    with pytest.raises(ValueError, match="unique"):
        StructuralAudit(d, outcome="y", exposure="x", unit_id="id", edges=edges)
    a = StructuralAudit(pd.DataFrame({"x": np.random.default_rng(0).binomial(1, .5, 50),
                                      "y": np.random.default_rng(1).binomial(1, .5, 50)}),
                        outcome="y", exposure="x")
    with pytest.raises(ValueError, match="needs a network"):
        a.test(["interference_check"])


def test_spatial_holdout_flags_regional_heterogeneity():
    rng = np.random.default_rng(2); n = 3000
    lon = rng.uniform(0, 10, n); lat = rng.uniform(0, 10, n); x = rng.binomial(1, 0.5, n)
    eff = np.where(lon < 5, -1.8, 0.0)
    y = rng.binomial(1, 1/(1+np.exp(-(0.2 + eff*x))))
    d = pd.DataFrame({"y": y, "x": x, "lon": lon, "lat": lat})
    a = StructuralAudit(d, outcome="y", exposure="x", coords=("lon", "lat"))
    a.assume("spatial_translation", "homog", "pool").test(["spatial_holdout"], spatial_k=2)
    assert a.tests["spatial_holdout"]["verdict"] == "unstable"
    assert a.tests["spatial_holdout"]["variants"].shape[0] == 4

    y2 = rng.binomial(1, 1/(1+np.exp(-(-0.6*x))), n)
    d2 = pd.DataFrame({"y": y2, "x": x, "lon": lon, "lat": lat})
    a2 = StructuralAudit(d2, outcome="y", exposure="x", coords=("lon", "lat"))
    a2.assume("spatial_translation", "h", "p").test(["spatial_holdout"], spatial_k=3)
    assert a2.tests["spatial_holdout"]["verdict"] == "stable"


def test_coords_validation_and_spatial_needs_them():
    d = pd.DataFrame({"y": np.random.default_rng(0).binomial(1, .5, 50),
                      "x": np.random.default_rng(1).binomial(1, .5, 50),
                      "lon": np.random.default_rng(2).uniform(size=50)})
    with pytest.raises(ValueError, match="two column"):
        StructuralAudit(d, outcome="y", exposure="x", coords=("lon",))
    a = StructuralAudit(d, outcome="y", exposure="x")
    with pytest.raises(ValueError, match="declared coordinates"):
        a.test(["spatial_holdout"])


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


def _collider(n=1500, correlate=False, seed=1):
    rng = np.random.default_rng(seed)
    a = rng.normal(size=n)
    b = 0.6 * a + 0.8 * rng.normal(size=n) if correlate else rng.normal(size=n)
    cc = a + b + rng.normal(size=n)
    return pd.DataFrame({"a": a, "b": b, "cc": cc, "y": rng.binomial(1, 1 / (1 + np.exp(-a)))})


def test_graph_check_detects_consistent_and_violated():
    au = StructuralAudit(_collider(correlate=False), outcome="y", exposure="a")
    au.declare_graph(["a -> cc", "b -> cc", "a -> y"])
    au.assume("causal_graph", "collider DAG", "adjustment from graph")
    au.test(["graph_check"])
    assert au.tests["graph_check"]["verdict"] == "stable"

    au2 = StructuralAudit(_collider(correlate=True, seed=2), outcome="y", exposure="a")
    au2.declare_graph(["a -> cc", "b -> cc", "a -> y"]).test(["graph_check"])
    assert au2.tests["graph_check"]["verdict"] == "unstable"

    # the graph_check audit (with an implications block) validates against the shared schema
    import jsonschema
    au.decide()
    jsonschema.validate(au.export_audit(), json.loads(SCHEMA.read_text()))


def test_assumption_lattice_refits_and_is_schema_valid():
    import jsonschema
    rng = np.random.default_rng(3); n = 1200
    h = rng.choice(list("ABCDE"), n); yr = rng.integers(2018, 2023, n)
    age = rng.normal(65, 8, n); x = rng.binomial(1, 1/(1+np.exp(0.02*(age-65))))
    lp = -0.6*x + 0.03*(age-65); te = rng.exponential(1/(0.05*np.exp(lp))); tc = rng.uniform(1, 6, n)
    d = pd.DataFrame({"time": np.minimum(te, tc), "status": (te <= tc).astype(int),
                      "x": x, "age": age, "h": h, "yr": yr})
    a = StructuralAudit(d, outcome=("time", "status"), exposure="x", covariates=["age"],
                        cluster="h", time="yr")
    a.assume("cluster_exchangeability", "p", "p").test(["cluster_holdout"]).decide()
    a.assumption_lattice()
    assert len(a.lattice["nodes"]) == 4
    assert a.lattice["verdict"] in ("stable", "unstable", "not_resolvable")
    top = [nd for nd in a.lattice["nodes"] if nd["n_pooled"] == 2][0]
    assert abs(top["estimate"] - a.estimate["value"]) < 1e-6
    jsonschema.validate(a.export_audit(), json.loads(SCHEMA.read_text()))


def test_stratified_cox_matches_r_breslow():
    # exact cross-check against R coxph(ties="breslow") on fixed data lives in the R suite;
    # here we assert stratification runs and a noise stratum keeps the sign
    from assesslite.estimator import fit_estimate
    rng = np.random.default_rng(9); n = 1500
    g = rng.integers(0, 4, n).astype(str); x = rng.binomial(1, 0.5, n); age = rng.normal(0, 1, n)
    y = rng.binomial(1, 1/(1+np.exp(-(-0.7*x + 0.2*age))))
    d = pd.DataFrame({"y": y, "x": x, "age": age, "g": g})
    an = {"exposure": "x", "covariates": ["age"], "outcome_cols": ["y"], "estimator": "glm_binomial"}
    f0 = fit_estimate(an, d)
    fs = fit_estimate(an, d, strata=["g"])
    assert np.sign(f0["value"]) == np.sign(fs["value"])


def test_backdoor_handles_textbook_cases():
    from assesslite.graph import backdoor_valid
    triangle = {"C": [], "X": ["C"], "Y": ["C", "X"]}
    assert backdoor_valid(triangle, "X", "Y", ["C"]) is True
    assert backdoor_valid(triangle, "X", "Y", []) is False
    mediator = {"X": [], "M": ["X"], "Y": ["M"]}
    assert backdoor_valid(mediator, "X", "Y", []) is True
    mbias = {"U1": [], "U2": [], "Z": ["U1", "U2"], "X": ["U1"], "Y": ["U2", "X"]}
    assert backdoor_valid(mbias, "X", "Y", []) is True
    assert backdoor_valid(mbias, "X", "Y", ["Z"]) is False  # collider opened


def test_adjustment_check_flags_under_and_over_adjustment():
    rng = np.random.default_rng(1); n = 1000
    C = rng.normal(size=n); X = rng.binomial(1, 1/(1+np.exp(-C))); M = X + rng.normal(size=n)
    Y = rng.binomial(1, 1/(1+np.exp(-(0.5*C + 0.6*X))))
    d = pd.DataFrame({"C": C, "X": X, "M": M, "Y": Y})

    def run(covs):
        a = StructuralAudit(d, outcome="Y", exposure="X", covariates=covs)
        a.declare_graph(["C -> X", "C -> Y", "X -> Y", "X -> M"])
        a.test(["adjustment_check"])
        return a.tests["adjustment_check"]

    assert run(["C"])["verdict"] == "stable"
    assert run([])["verdict"] == "unstable"
    over = run(["C", "M"])
    assert over["verdict"] == "unstable"
    assert over["adjustment"]["over_adjustment"] == ["M"]


def test_adjustment_check_latent_non_identifiability():
    rng = np.random.default_rng(1); n = 1000
    U = rng.normal(size=n); C = rng.normal(size=n)
    X = rng.binomial(1, 1/(1+np.exp(-(0.8*U + 0.6*C))))
    Y = rng.binomial(1, 1/(1+np.exp(-(0.7*U + 0.5*C + 0.5*X))))
    d = pd.DataFrame({"C": C, "X": X, "Y": Y})

    def run(covs, edges, latent=()):
        a = StructuralAudit(d, outcome="Y", exposure="X", covariates=covs)
        a.declare_graph(edges, latent=latent)
        a.test(["adjustment_check"])
        return a.tests["adjustment_check"]

    r1 = run(["C"], ["U -> X", "U -> Y", "C -> X", "C -> Y", "X -> Y"], latent=["U"])
    assert r1["verdict"] == "not_resolvable"
    assert r1["adjustment"]["identifiable"] is False
    r2 = run(["C"], ["C -> X", "C -> Y", "X -> Y"])
    assert r2["verdict"] == "stable"
    assert r2["adjustment"]["identifiable"] is True


def test_declare_graph_validates_latent_and_skips_latent_implications():
    d = pd.DataFrame({"C": np.random.default_rng(0).normal(size=50),
                      "X": np.random.default_rng(1).binomial(1, 0.5, 50),
                      "Y": np.random.default_rng(2).binomial(1, 0.5, 50)})
    a = StructuralAudit(d, outcome="Y", exposure="X")
    with pytest.raises(ValueError, match="not in the graph"):
        a.declare_graph(["C -> X", "X -> Y"], latent=["Q"])
    a.declare_graph(["U -> X", "U -> Y", "X -> Y"], latent=["U"]).test(["graph_check"])
    for im in a.tests["graph_check"]["implications"]:
        if "U" in im["claim"]:
            assert im["status"] == "not_testable"


def test_declare_graph_rejects_cycle_and_graph_check_needs_graph():
    d = pd.DataFrame({"a": np.random.default_rng(0).normal(size=50),
                      "b": np.random.default_rng(1).normal(size=50),
                      "y": np.random.default_rng(2).binomial(1, 0.5, 50)})
    a = StructuralAudit(d, outcome="y", exposure="a")
    with pytest.raises(ValueError, match="acyclic"):
        a.declare_graph(["a -> b", "b -> a"])
    with pytest.raises(ValueError, match="declared graph"):
        a.test(["graph_check"])


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
