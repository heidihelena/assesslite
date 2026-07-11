"""HTML report (AssessLite core spec v0.1, spec/reporting/report-structure.md).
Self-contained file, no external assets. Section order is the argument: structure,
then ledger, then estimate, then attacks, then decision. Ported from the R engine.
"""
from __future__ import annotations

from .export import audit_as_list

_CSS = """
:root { --ink:#1a2330; --muted:#5b6673; --line:#d9dde3; --bg:#fafaf8; --card:#ffffff;
        --accent:#33586e; --ok:#2e6e4e; --bad:#a33d2e; --nr:#8a6d1f; }
body { font: 15px/1.55 'Avenir Next', 'Segoe UI', system-ui, sans-serif;
       color: var(--ink); background: var(--bg); margin: 0; }
main { max-width: 860px; margin: 0 auto; padding: 40px 24px 80px; }
h1 { font-size: 1.5rem; font-weight: 600; margin: 0 0 4px; }
h2 { font-size: 1.05rem; font-weight: 600; margin: 36px 0 10px; color: var(--accent);
     text-transform: lowercase; letter-spacing: .02em; }
.meta { color: var(--muted); font-size: .85rem; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; background: var(--card); }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: .8rem; }
.chip { display: inline-block; padding: 1px 9px; border-radius: 10px; font-size: .8rem;
        color: #fff; white-space: nowrap; }
.chip.ok { background: var(--ok); } .chip.bad { background: var(--bad); } .chip.nr { background: var(--nr); }
.decision { border-left: 4px solid var(--accent); background: var(--card);
            padding: 14px 18px; margin-top: 8px; }
.decision.abstain { border-color: var(--bad); } .decision.proceed { border-color: var(--ok); }
.decision.conditional { border-color: var(--nr); }
.status { font-weight: 700; text-transform: uppercase; letter-spacing: .06em; font-size: .85rem; }
.reading { color: var(--muted); font-size: .88rem; margin: 6px 0 0; }
.draft { background: var(--card); border: 1px dashed var(--line); padding: 12px 16px;
         font-size: .9rem; color: var(--ink); }
"""


def _esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(x, d: int = 3) -> str:
    return f"{float(x):.{d}f}"


def _chip(v: str) -> str:
    cls = {"stable": "ok", "unstable": "bad", "not_resolvable": "nr"}[v]
    lab = {"stable": "stable", "unstable": "unstable", "not_resolvable": "not resolvable at this n"}[v]
    return f'<span class="chip {cls}">{lab}</span>'


def _lattice_svg(L) -> str:
    fill = {"consistent": "#2e6e4e", "attenuated": "#8a6d1f", "reversed": "#a33d2e"}
    k = len(L["axes"])
    nds = L["nodes"]
    W, H, pad = 540, 60 + k * 90, 34
    lev = [nd["n_pooled"] for nd in nds]
    pos = []
    for idx, nd in enumerate(nds):
        row_idx = [i for i, lv in enumerate(lev) if lv == lev[idx]]
        m = len(row_idx); i = row_idx.index(idx)
        y = H - pad - lev[idx] * ((H - 2 * pad) / max(k, 1))
        x = W / 2 if m == 1 else pad + i * (W - 2 * pad) / (m - 1)
        pos.append({"x": x, "y": y, "pooled": sorted(nd["pooled"]),
                    "status": nd["status"], "est": nd["estimate"]})
    edges = ""
    for a in pos:
        for b in pos:
            if len(b["pooled"]) == len(a["pooled"]) + 1 and all(p in b["pooled"] for p in a["pooled"]):
                edges += (f"<line x1='{a['x']:.0f}' y1='{a['y']:.0f}' x2='{b['x']:.0f}' "
                          f"y2='{b['y']:.0f}' stroke='#c7ccd3'/>")
    circles = ""
    for p in pos:
        lab = "none" if not p["pooled"] else "+".join(w[:4] for w in p["pooled"])
        circles += (f"<circle cx='{p['x']:.0f}' cy='{p['y']:.0f}' r='17' fill='{fill[p['status']]}'/>"
                    f"<text x='{p['x']:.0f}' y='{p['y']+2:.0f}' text-anchor='middle' font-size='8' fill='#fff'>{_esc(lab)}</text>"
                    f"<text x='{p['x']:.0f}' y='{p['y']+32:.0f}' text-anchor='middle' font-size='9' fill='#5b6673'>{_fmt(p['est'], 2)}</text>")
    return f"<svg viewBox='0 0 {W} {H}' width='100%' style='max-width:540px'>{edges}{circles}</svg>"


def _lattice_html(L, scale) -> str:
    if not L or not L.get("nodes"):
        return ""
    chip_of = {"consistent": "ok", "attenuated": "nr", "reversed": "bad"}
    rows = []
    for nd in L["nodes"]:
        pooled = ", ".join(x.replace("_", " ") for x in nd["pooled"]) if nd["pooled"] else "nothing"
        rows.append(
            f"<tr><td>pool: {_esc(pooled)}</td>"
            f"<td>{_fmt(nd['estimate'])} [{_fmt(nd['ci_low'])}, {_fmt(nd['ci_high'])}]</td>"
            f"<td>{nd['n']}</td>"
            f"<td><span class='chip {chip_of[nd['status']]}'>{_esc(nd['status'])}</span></td></tr>")
    axes = ", ".join(x.replace("_", " ") for x in L["axes"])
    return (f"<h2>assumption lattice {_chip(L['verdict'])}</h2>"
            f"<p class='meta'>pooling axes: {_esc(axes)} (each node pools some axes and stratifies the rest)</p>"
            f"{_lattice_svg(L)}"
            f"<table><tr><th>node</th><th>estimate ({_esc(scale)})</th><th>n</th><th>status</th></tr>"
            f"{''.join(rows)}</table><p class='reading'>{_esc(L['reading'])}</p>")


def _limitations(assessment) -> str:
    d = assessment.decision
    if d["status"] == "proceed":
        base = ("The invariance assumptions relied on for pooling ("
                + "; ".join(x.replace("_", " ") for x in d["load_bearing"])
                + ") were each attacked by transformation tests and came back stable at the "
                "precision the data allowed.")
    elif d["status"] == "conditional":
        base = ("The following invariance assumptions were relied on but could not be assessed, or "
                "were not resolvable at this sample size: "
                + "; ".join(x.replace("_", " ") for x in d["exposed_surface"])
                + ". Conclusions are conditional on these claims holding.")
    else:
        base = (f"The analysis abstains from a pooled conclusion: the {d['broken_by']} attack showed "
                "that a relied-on invariance does not hold up, and the pooling it licenses has no "
                "basis in this data.")
    return (base + " Stability verdicts assess whether the conclusion survived the attacks that were "
            "run; they do not establish the truth of the assumptions. [Draft for the analyst to edit; "
            "generated by assesslite-python, core spec 0.1.]")


def render_report(assessment, path: str) -> str:
    if assessment.decision is None:
        raise RuntimeError("run decide() before rendering; a report without a decision is not complete")
    a = assessment.analysis
    s = assessment.structure
    e = assessment.estimate
    d = assessment.decision
    al = audit_as_list(assessment)
    prov = al["provenance"]

    ledger_rows = "\n".join(
        "<tr><td><strong>{inv}</strong><br><span class='meta'>{st}</span></td>"
        "<td>{rat}</td><td>{lic}</td><td>{v}</td></tr>".format(
            inv=_esc(l["invariance"].replace("_", " ")), st=_esc(l["status"]),
            rat=_esc(l["rationale"]), lic=_esc(l["licenses"]),
            v=(_chip(l["verdict"]) if l["tested"] else
               ("<span class='meta'>untested</span>" if l["status"] == "assumed" else "")))
        for l in assessment.ledger)

    blocks = []
    for t in assessment.tests.values():
        if t.get("scenarios") is not None:
            import math as _m
            sc = t["scenarios"]
            rrs = sorted({c["rr_uy"] for c in sc["cells"]})
            dls = sorted({c["delta"] for c in sc["cells"]})
            cellmap = {(c["rr_uy"], c["delta"]): c for c in sc["cells"]}
            header = ("<tr><th>&Delta; prevalence \\ RR<sub>UY</sub></th>"
                      + "".join(f"<th>{rr:.1f}</th>" for rr in rrs) + "</tr>")
            rows = []
            for dl in dls:
                tds = []
                for rr in rrs:
                    c = cellmap[(rr, dl)]
                    bg = " style='background:#f3d9d4'" if c["tips"] else ""
                    tds.append(f"<td{bg}>{_m.exp(c['adjusted_estimate']):.2f}</td>")
                rows.append(f"<tr><th>{dl:.2f}</th>{''.join(tds)}</tr>")
            tgt = "no effect (null)" if sc["target"] is None else f"ratio {sc['target']:.2f}"
            cap = (f"<p class='meta'>adjusted {_esc(a['scale'])} (ratio scale) after an unmeasured "
                   f"confounder at prevalence {sc['confounder_prevalence']:.2f}; shaded cells tip past "
                   f"{tgt}. Plausible bound: RR<sub>UY</sub> &le; {sc['plausible_rr_uy']:.1f}, "
                   f"&Delta; &le; {sc['plausible_delta']:.2f}</p>")
            blocks.append(
                "<h2>attack: {test} {chip}</h2><p class='meta'>probes: {inv}</p>{cap}"
                "<table>{hdr}{body}</table><p class='reading'>{reading}</p>".format(
                    test=_esc(t["test"].replace("_", " ")), chip=_chip(t["verdict"]),
                    inv=_esc(t["invariance"].replace("_", " ")), cap=cap, hdr=header,
                    body="".join(rows), reading=_esc(t["reading"])))
            continue
        if t.get("spillover") is not None:
            sp = t["spillover"]
            nb = ("not estimated" if sp["neighbor_exposure_coef"] is None
                  else f"{sp['neighbor_exposure_coef']:.3f} [{sp['ci_low']:.3f}, {sp['ci_high']:.3f}]")
            adj_est = "&mdash;" if sp["exposure_estimate_adjusted"] is None else f"{sp['exposure_estimate_adjusted']:.3f}"
            body = (
                "<table>"
                f"<tr><th>neighbour-exposure effect</th><td>{nb}</td></tr>"
                f"<tr><td>exposure estimate (ignoring neighbours)</td><td>{sp['exposure_estimate']:.3f}</td></tr>"
                f"<tr><td>exposure estimate (accounting for neighbours)</td><td>{adj_est}</td></tr>"
                f"<tr><td>units with &ge;1 neighbour</td><td>{sp['n_with_neighbors']}</td></tr></table>")
            blocks.append(
                "<h2>attack: {test} {chip}</h2><p class='meta'>probes: {inv}</p>{body}"
                "<p class='reading'>{reading}</p>".format(
                    test=_esc(t["test"].replace("_", " ")), chip=_chip(t["verdict"]),
                    inv=_esc(t["invariance"].replace("_", " ")), body=body,
                    reading=_esc(t["reading"])))
            continue
        if t.get("adjustment") is not None:
            aj = t["adjustment"]
            fmt = lambda s: _esc(", ".join(s)) if s else "&#8709;"
            body = (
                "<table>"
                f"<tr><th>exposure &rarr; outcome</th><td>{_esc(aj['exposure'])} &rarr; {_esc(str(aj['outcome']))}</td></tr>"
                f"<tr><td>adjusted for</td><td>{{{fmt(aj['adjusted'])}}}</td></tr>"
                f"<tr><td>sufficient set (from graph)</td><td>{{{fmt(aj['sufficient_set'])}}}</td></tr>"
                f"<tr><td>missing (graph says adjust, you did not)</td><td>{{{fmt(aj['missing'])}}}</td></tr>"
                f"<tr><td>over-adjustment (descendant of exposure)</td><td>{{{fmt(aj['over_adjustment'])}}}</td></tr></table>")
            blocks.append(
                "<h2>attack: {test} {chip}</h2><p class='meta'>probes: {inv}</p>{body}"
                "<p class='reading'>{reading}</p>".format(
                    test=_esc(t["test"].replace("_", " ")), chip=_chip(t["verdict"]),
                    inv=_esc(t["invariance"].replace("_", " ")), body=body,
                    reading=_esc(t["reading"])))
            continue
        if t.get("implications") is not None:
            chip_of = {"consistent": "ok", "violated": "bad",
                       "not_resolvable": "nr", "not_testable": "nr"}
            irows = []
            for im in t["implications"]:
                if im["partial_r"] is None:
                    val = "—"
                else:
                    pv = "NA" if im["p_value"] is None else f"{im['p_value']:.2g}"
                    val = f"r = {im['partial_r']:.3f}, p = {pv}"
                irows.append(
                    f"<tr><td>{_esc(im['claim'])}</td><td>{val}</td>"
                    f"<td><span class='chip {chip_of[im['status']]}'>{_esc(im['status'].replace('_', ' '))}</span></td></tr>")
            body = ("<table><tr><th>implied independence</th><th>partial correlation</th>"
                    "<th>outcome</th></tr>" + "\n".join(irows) + "</table>")
            blocks.append(
                "<h2>attack: {test} {chip}</h2><p class='meta'>probes: {inv}</p>{body}"
                "<p class='reading'>{reading}</p>".format(
                    test=_esc(t["test"].replace("_", " ")), chip=_chip(t["verdict"]),
                    inv=_esc(t["invariance"].replace("_", " ")), body=body,
                    reading=_esc(t["reading"])))
            continue
        if t.get("sensitivity") is not None:
            sv = t["sensitivity"]
            e_ci = "1 (interval includes no effect)" if abs(sv["e_value_ci"] - 1) < 1e-9 else f"{sv['e_value_ci']:.2f}"
            body = (
                "<table><tr><th>quantity</th><th>value</th></tr>"
                f"<tr><td>ratio estimate</td><td>{sv['rr_point']:.2f} [{sv['rr_ci_low']:.2f}, {sv['rr_ci_high']:.2f}]</td></tr>"
                f"<tr><td>E-value (point estimate)</td><td>{sv['e_value_point']:.2f}</td></tr>"
                f"<tr><td>E-value (interval limit nearest null)</td><td>{e_ci}</td></tr>"
                f"<tr><td>plausible confounding benchmark</td><td>{sv['benchmark']:.2f}</td></tr></table>")
            blocks.append(
                "<h2>attack: {test} {chip}</h2><p class='meta'>probes: {inv}</p>{body}"
                "<p class='reading'>{reading}</p>".format(
                    test=_esc(t["test"].replace("_", " ")), chip=_chip(t["verdict"]),
                    inv=_esc(t["invariance"].replace("_", " ")), body=body,
                    reading=_esc(t["reading"])))
            continue
        v = t["variants"]
        rows = "\n".join(
            "<tr><td>{lab}</td><td>{est}</td><td>[{lo}, {hi}]</td><td>{n}</td></tr>".format(
                lab=_esc(r["label"]), est=_fmt(r["estimate"]), lo=_fmt(r["ci_low"]),
                hi=_fmt(r["ci_high"]), n=int(r["n"]))
            for _, r in v.iterrows())
        failed = (f"<p class='meta'>{t['n_failed']} variant refit(s) failed and are not shown.</p>"
                  if t["n_failed"] > 0 else "")
        blocks.append(
            "<h2>attack: {test} {chip}</h2><p class='meta'>probes: {inv}</p>"
            "<table><tr><th>variant</th><th>estimate</th><th>95% interval</th><th>n</th></tr>{rows}</table>"
            "{failed}<p class='reading'>{reading}</p>".format(
                test=_esc(t["test"].replace("_", " ")), chip=_chip(t["verdict"]),
                inv=_esc(t["invariance"].replace("_", " ")), rows=rows, failed=failed,
                reading=_esc(t["reading"])))
    test_blocks = "\n".join(blocks)

    surface = (f"<p><strong>Exposed surface</strong> (relied on, not settled): "
               f"{_esc('; '.join(x.replace('_', ' ') for x in d['exposed_surface']))}</p>"
               if d["exposed_surface"] else "")
    load_b = (f"<p><strong>Load-bearing</strong> (attacked, stable): "
              f"{_esc('; '.join(x.replace('_', ' ') for x in d['load_bearing']))}</p>"
              if d["load_bearing"] else "")
    broken = f"<p><strong>Broken by</strong>: {_esc(d['broken_by'])}</p>" if d["broken_by"] else ""

    lattice_html = _lattice_html(assessment.lattice, a["scale"])

    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>structural audit — {_esc(a['estimand'])}</title><style>{_CSS}</style></head><body><main>
<h1>Structural audit</h1>
<p class='meta'>{_esc(a['estimand'])} · unit: {_esc(a['unit'])} · {_esc(a['estimator'])} ·
 engine {_esc(prov['engine'])} {_esc(prov['engine_version'])} · core spec {_esc(prov['spec_version'])} ·
 {_esc(prov['created'])} · data {prov['data_fingerprint']['n_rows']} × {prov['data_fingerprint']['n_cols']},
 md5 {_esc(prov['data_fingerprint']['md5'][:12])}</p>

<h2>declared structure</h2>
<table>
<tr><th>cluster</th><td>{_esc(s['cluster'] if s['cluster'] else 'none declared')}</td></tr>
<tr><th>time</th><td>{_esc(s['time'] if s['time'] else 'none declared')}</td></tr>
<tr><th>subgroups</th><td>{_esc(', '.join(s['subgroups']) if s['subgroups'] else 'none declared')}</td></tr>
<tr><th>covariates</th><td>{_esc(', '.join(a['covariates']) if a['covariates'] else 'none')}</td></tr>
</table>

<h2>invariance ledger</h2>
<table><tr><th>claim</th><th>rationale</th><th>licenses</th><th>verdict</th></tr>{ledger_rows}</table>

<h2>full-sample estimate</h2>
<table><tr><th>scale</th><th>estimate</th><th>95% interval</th><th>n</th></tr>
<tr><td>{_esc(a['scale'])}</td><td>{_fmt(e['value'])}</td><td>[{_fmt(e['ci_low'])}, {_fmt(e['ci_high'])}]</td><td>{e['n']}</td></tr></table>

{test_blocks}

<h2>decision</h2>
<div class='decision {d['status']}'><span class='status'>{d['status'].upper()}</span>
<p>{_esc(d['rationale'])}</p>{load_b}{surface}{broken}</div>

{lattice_html}

<h2>limitations text (draft)</h2>
<div class='draft'>{_esc(_limitations(assessment))}</div>
</main></body></html>"""

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path
