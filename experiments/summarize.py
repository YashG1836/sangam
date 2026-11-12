"""Aggregate results/runs.jsonl (+ results/sweep.jsonl) into summary tables, figures and
site/data.json for the demo page. Every number shown anywhere comes from this script."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sangam.data import BANKS, BANK_SHORT  # noqa: E402

RES = ROOT / "results"
FIG = ROOT / "site" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, GRAY, INK, INK2, GRID = "#2a78d6", "#eb6834", "#a3a29c", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "figure.dpi": 200, "savefig.bbox": "tight", "legend.frameon": False})

METRICS = ["auc", "tpr", "tpr_senior", "tpr_non_senior", "fpr_senior", "fpr_non_senior", "fpr_ratio"]
SCEN_LABEL = {
    "none": "No attack",
    "label_flip": "Label-flip (2 banks)",
    "sign_flip": "Model poisoning (2 banks)",
    "targeted_senior": "Senior-targeted (2 banks)",
    "label_flip_majority": "Label-flip (4 of 7 banks)",
    "sign_flip_majority": "Model poisoning (4 of 7 banks)",
    "targeted_senior_majority": "Senior-targeted (4 of 7 banks)",
}


def load(p):
    return [json.loads(l) for l in open(p)] if Path(p).exists() else []


def ms(vals):
    a = np.array(vals, float)
    return float(a.mean()), float(a.std(ddof=0))


def attacker_share(run):
    mal = run.get("malicious") or []
    ws = [h["weights"] for h in run["history"] if h.get("weights")]
    if not mal or not ws:
        return None
    return float(np.mean([sum(w[i] for i in mal) for w in ws]))


def main():
    runs = load(RES / "runs.jsonl")
    groups = defaultdict(list)
    for r in runs:
        groups[(r["attack"], r["label"])].append(r)

    table = {}
    for (scen, label), rs in groups.items():
        row = {m: ms([r["final"][m] for r in rs]) for m in METRICS}
        sh = [attacker_share(r) for r in rs]
        row["attacker_weight"] = ms(sh) if all(s is not None for s in sh) else None
        row["n"] = len(rs)
        bt = defaultdict(list)
        for r in rs:
            for b, v in r["final"].get("bank_tpr", {}).items():
                bt[int(b)].append(v)
        row["bank_tpr"] = {b: ms(v) for b, v in sorted(bt.items())}
        table.setdefault(scen, {})[label] = row

    order = ["Local only", "Centralised (pooled data)", "FedAvg", "Median", "Trimmed-Mean", "Multi-Krum", "FLTrust",
             "FedAvg + Fair", "Multi-Krum + Fair", "FLTrust + Fair", "Sangam-Trust (no fairness)", "Sangam (full)"]
    scen_order = [s for s in SCEN_LABEL if s in table]

    # ---------------------------------------------------------------- markdown tables
    lines = ["# Sangam benchmark results", "",
             f"Seeds per cell: {max(r['n'] for t in table.values() for r in t.values())}. Mean ± std. "
             "TPR = share of fraudulent account openings caught at a 5% false-positive rate (BAF protocol). "
             "FPR ratio = predictive equality between applicants aged 50+ and under 50 (1.0 = equal).", ""]
    for scen in scen_order:
        lines += [f"## {SCEN_LABEL[scen]}", "",
                  "| Method | AUC | Fraud caught (TPR) | Senior fraud caught | Wrongly flagged: 50+ | Wrongly flagged: <50 | FPR ratio | Attacker weight |",
                  "|---|---|---|---|---|---|---|---|"]
        for lab in order:
            if lab not in table[scen]:
                continue
            r = table[scen][lab]
            f = lambda k, p=3: f"{r[k][0]:.{p}f} ± {r[k][1]:.{p}f}"
            aw = f"{100*r['attacker_weight'][0]:.0f}%" if r["attacker_weight"] else "–"
            lines.append(f"| {lab} | {f('auc')} | {f('tpr')} | {f('tpr_senior')} | {100*r['fpr_senior'][0]:.1f}% | "
                         f"{100*r['fpr_non_senior'][0]:.1f}% | {f('fpr_ratio',2)} | {aw} |")
        lines.append("")
    (RES / "summary.md").write_text("\n".join(lines))

    # ---------------------------------------------------------------- sweep
    sweep = load(RES / "sweep.jsonl")
    sw = defaultdict(list)
    for r in sweep:
        sw[(r["attack"], r["fair_max"])].append(r["final"])
    sweep_rows = []
    for (scen, fm), fs in sorted(sw.items()):
        sweep_rows.append(dict(scenario=scen, fair_max=fm, **{m: ms([f[m] for f in fs]) for m in METRICS}))

    # ---------------------------------------------------------------- alignment ablation
    abl = defaultdict(list)
    for r in load(RES / "ablation.jsonl"):
        abl[(r["attack"], r["align"])].append(r)
    abl_rows = [dict(scenario=sc, align=al, tpr=ms([r["final"]["tpr"] for r in rs]),
                     attacker_weight=ms([r["attacker_weight"] for r in rs]), n=len(rs))
                for (sc, al), rs in sorted(abl.items())]

    # ---------------------------------------------------------------- figures
    clean = table.get("none", {})
    if clean:
        fig_bank_uplift(clean)
        fig_fairness(clean)
    fig_robustness(table, scen_order)
    if "targeted_senior_majority" in table:
        fig_targeted(table)
    if sweep_rows:
        fig_tradeoff(sweep_rows)

    # ---------------------------------------------------------------- site data
    hist = {}
    for r in runs:
        if r["seed"] == 0 and r["history"]:
            hist.setdefault(r["attack"], {})[r["label"]] = [
                {k: h[k] for k in ("round", "tpr", "tpr_senior", "fpr_ratio", "auc", "weights", "fpr_senior", "fpr_non_senior")}
                for h in r["history"]]
    site = dict(banks=BANKS, bank_short=BANK_SHORT, scenarios=SCEN_LABEL, table=table, history=hist,
                sweep=sweep_rows, malicious={r["attack"]: r.get("malicious", []) for r in runs})
    (ROOT / "site").mkdir(exist_ok=True)
    (ROOT / "site" / "data.js").write_text("window.SANGAM_DATA = " + json.dumps(site) + ";\n")
    from sangam.data import build, describe
    tr, *_ = build(ROOT.parent / "data" / "base.parquet", seed=0)
    (RES / "bank_stats.json").write_text(describe(tr).to_json(orient="records"))
    (RES / "summary.json").write_text(json.dumps(dict(table=table, sweep=sweep_rows, ablation=abl_rows), indent=1))
    print("\n".join(lines))
    if sweep_rows:
        print("\nSweep:")
        for s in sweep_rows:
            print(s["scenario"], s["fair_max"], {m: round(s[m][0], 3) for m in ("tpr", "tpr_senior", "fpr_ratio", "fpr_senior")})


def fig_bank_uplift(clean):
    loc, sg = clean["Local only"]["bank_tpr"], clean["Sangam (full)"]["bank_tpr"]
    fa = clean["FedAvg"]["bank_tpr"]
    y = np.arange(len(BANKS))
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    h = 0.36
    ax.barh(y - h / 2, [loc[b][0] * 100 for b in range(len(BANKS))], h, color=GRAY, label="Bank alone (today)")
    ax.barh(y + h / 2, [sg[b][0] * 100 for b in range(len(BANKS))], h, color=BLUE, label="Sangam consortium")
    for b in range(len(BANKS)):
        ax.text(sg[b][0] * 100 + 0.6, b + h / 2, f"{sg[b][0]*100:.0f}%", va="center", fontsize=8, color=INK)
        ax.text(loc[b][0] * 100 + 0.6, b - h / 2, f"{loc[b][0]*100:.0f}%", va="center", fontsize=8, color=INK2)
    ax.set_yticks(y, BANKS)
    ax.invert_yaxis()
    ax.set_xlabel("Fraudulent account openings caught at 5% false-alarm rate (%)")
    ax.set_xlim(0, 62)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=8)
    fig.savefig(FIG / "bank_uplift.png")
    plt.close(fig)


def fig_fairness(clean):
    labs = [("Local only", "Bank alone"), ("FedAvg", "Standard federated"), ("Sangam (full)", "Sangam")]
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    x = np.arange(len(labs))
    w = 0.36
    s = [clean[l]["fpr_senior"][0] * 100 for l, _ in labs]
    n = [clean[l]["fpr_non_senior"][0] * 100 for l, _ in labs]
    ax.bar(x - w / 2, s, w, color=ORANGE, label="Genuine applicants aged 50+")
    ax.bar(x + w / 2, n, w, color=BLUE, label="Genuine applicants under 50")
    for i in range(len(labs)):
        ax.text(x[i] - w / 2, s[i] + 0.2, f"{s[i]:.1f}%", ha="center", fontsize=8, color=INK)
        ax.text(x[i] + w / 2, n[i] + 0.2, f"{n[i]:.1f}%", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, [b for _, b in labs])
    ax.set_ylabel("Wrongly flagged as fraud (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=8, loc="upper right")
    fig.savefig(FIG / "fairness.png")
    plt.close(fig)


def fig_robustness(table, scen_order):
    meths = ["FedAvg", "Median", "Trimmed-Mean", "Multi-Krum", "FLTrust", "Sangam (full)"]
    M = np.array([[table[s].get(m, {"tpr": (np.nan, 0)})["tpr"][0] * 100 for s in scen_order] for m in meths])
    fig, ax = plt.subplots(figsize=(8.4, 3.3))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("b", ["#f0efec", "#86b6ef", "#2a78d6", "#184f95"])
    ax.imshow(M, cmap=cmap, vmin=0, vmax=55, aspect="auto")
    for i in range(len(meths)):
        for j in range(len(scen_order)):
            v = M[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=9, color="white" if v > 35 else INK)
    ax.set_xticks(range(len(scen_order)), [SCEN_LABEL[s].replace(" (", "\n(") for s in scen_order], fontsize=7.5)
    ax.set_yticks(range(len(meths)), meths)
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("Fraud caught (%) at 5% false-alarm rate, by attack scenario", fontsize=10, color=INK, loc="left")
    fig.savefig(FIG / "robustness.png")
    plt.close(fig)


def fig_targeted(table):
    t, c = table["targeted_senior_majority"], table["none"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.8, 3.3))
    m1 = ["FedAvg", "Multi-Krum", "FLTrust", "Sangam-Trust (no fairness)"]
    n1 = ["FedAvg", "Multi-Krum", "FLTrust", "Sangam\n(trust only)"]
    drop = [100 * (c[m]["tpr_senior"][0] - t[m]["tpr_senior"][0]) for m in m1]
    cols = [BLUE if m.startswith("Sangam") else GRAY for m in m1]
    a1.bar(n1, [max(0, d) for d in drop], color=cols, width=0.6)
    for i, d in enumerate(drop):
        a1.text(i, max(0, d) + 1.2, f"{d:.0f} pts", ha="center", fontsize=8, color=INK)
    a1.set_ylabel("Senior fraud capture lost\n(percentage points)")
    a1.set_ylim(0, 70)
    a1.set_title("Without fairness controller", fontsize=9, color=INK2, loc="left")
    a1.grid(axis="x", visible=False)
    a1.tick_params(axis="x", labelsize=8)
    m2 = ["FedAvg + Fair", "Multi-Krum + Fair", "FLTrust + Fair", "Sangam (full)"]
    n2 = ["FedAvg\n+ Fair", "Multi-Krum\n+ Fair", "FLTrust\n+ Fair", "Sangam"]
    x = np.arange(len(m2)); w = 0.36
    before = [c[m]["fpr_ratio"][0] for m in m2]
    after = [t[m]["fpr_ratio"][0] for m in m2]
    a2.bar(x - w / 2, before, w, color=GRAY, label="No attack")
    a2.bar(x + w / 2, after, w, color=[BLUE if m.startswith("Sangam") else ORANGE for m in m2], label="Under attack")
    for i in range(len(m2)):
        a2.text(x[i] + w / 2, after[i] + 0.02, f"{after[i]:.2f}", ha="center", fontsize=8, color=INK)
    a2.set_xticks(x, [f"{n}\n(attackers {100*t[m]['attacker_weight'][0]:.0f}%)" for n, m in zip(n2, m2)], fontsize=7.5)
    a2.set_ylim(0, 1.15)
    a2.set_ylabel("Fairness ratio (1.0 = equal)")
    a2.set_title("With fairness controller", fontsize=9, color=INK2, loc="left")
    a2.grid(axis="x", visible=False)
    a2.legend(fontsize=7.5, loc="upper right")
    fig.suptitle("Senior-targeted poisoning by 4 of 7 banks", fontsize=10, x=0.01, ha="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "targeted.png")
    plt.close(fig)


def fig_tradeoff(rows):
    rows = [r for r in rows if r["scenario"] == "none"]
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    x = [r["fpr_ratio"][0] for r in rows]
    y = [r["tpr"][0] * 100 for r in rows]
    ax.plot(x, y, color=BLUE, lw=2, marker="o", ms=6)
    for r, xi, yi in zip(rows, x, y):
        ax.annotate(f"λmax={r['fair_max']:g}", (xi, yi), textcoords="offset points", xytext=(6, 4), fontsize=7.5, color=INK2)
    ax.set_xlabel("Fairness: FPR ratio, 50+ vs under 50 (1.0 = equal)")
    ax.set_ylabel("Fraud caught (%)")
    fig.savefig(FIG / "tradeoff.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
