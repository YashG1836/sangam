"""Build the technical report, pitch deck and team-details sheet (HTML -> PDF via headless
Chrome). All numbers are read from results/summary.json; nothing is typed by hand.

    python docs/build_docs.py            # writes site/*.pdf and docs/*.html
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, SITE = ROOT / "docs", ROOT / "site"
sys.path.insert(0, str(ROOT / "src"))
from sangam.data import BANKS  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
S = json.loads((ROOT / "results" / "summary.json").read_text())
T, SW, AB = S["table"], S["sweep"], S.get("ablation", [])
TEAM = json.loads((DOCS / ("team.json" if (DOCS / "team.json").exists() else "team.example.json")).read_text())
BANKSTATS = json.loads((ROOT / "results" / "bank_stats.json").read_text())


def g(scen, lab, k, i=0):
    return T[scen][lab][k][i]


def p(x, d=1):
    return f"{100 * x:.{d}f}%"


def pm(scen, lab, k, d=1):
    return f"{100 * g(scen, lab, k):.{d}f} ± {100 * g(scen, lab, k, 1):.{d}f}"


# ------------------------------------------------------------------ headline numbers
N = {}
N["loc"] = g("none", "Local only", "tpr")
N["fed"] = g("none", "FedAvg", "tpr")
N["cen"] = g("none", "Centralised (pooled data)", "tpr")
N["sg"] = g("none", "Sangam (full)", "tpr")
N["sgt"] = g("none", "Sangam-Trust (no fairness)", "tpr")
N["up_sg"] = N["sg"] / N["loc"] - 1
N["up_fed"] = N["fed"] / N["loc"] - 1
bl, bs = T["none"]["Local only"]["bank_tpr"], T["none"]["Sangam (full)"]["bank_tpr"]
N["bank_up_min"] = min(bs[b][0] - bl[b][0] for b in bl)
N["bank_up_max"] = max(bs[b][0] - bl[b][0] for b in bl)
N["fed_fs"], N["fed_fn"] = g("none", "FedAvg", "fpr_senior"), g("none", "FedAvg", "fpr_non_senior")
N["sg_fs"], N["sg_fn"] = g("none", "Sangam (full)", "fpr_senior"), g("none", "Sangam (full)", "fpr_non_senior")
N["fed_ratio"], N["sg_ratio"] = g("none", "FedAvg", "fpr_ratio"), g("none", "Sangam (full)", "fpr_ratio")
N["loc_ratio"] = g("none", "Local only", "fpr_ratio")
N["fed_mult"] = N["fed_fs"] / N["fed_fn"]
N["seniors_saved_per_lakh"] = (N["fed_fs"] - N["sg_fs"]) * 1e5
MAJ = "sign_flip_majority"
N["maj_sg"] = g(MAJ, "Sangam (full)", "tpr")
N["maj_best_dist"] = max(g(MAJ, m, "tpr") for m in ("FedAvg", "Median", "Trimmed-Mean", "Multi-Krum"))
TG = "targeted_senior_majority"
N["tg_clean_sen"] = g("none", "FedAvg", "tpr_senior")
N["tg_clean_sen_sg"] = g("none", "Sangam-Trust (no fairness)", "tpr_senior")
for k, lab in (("fed", "FedAvg"), ("krum", "Multi-Krum"), ("flt", "FLTrust"), ("sgt", "Sangam-Trust (no fairness)"), ("sg", "Sangam (full)"), ("fltf", "FLTrust + Fair")):
    N[f"tg_{k}_sen"] = g(TG, lab, "tpr_senior")
    aw = T[TG][lab]["attacker_weight"]
    N[f"tg_{k}_aw"] = aw[0] if aw else None
    N[f"tg_{k}_drop"] = g("none", lab, "tpr_senior") - g(TG, lab, "tpr_senior")
    N[f"tg_{k}_ratio"], N[f"clean_{k}_ratio"] = g(TG, lab, "fpr_ratio"), g("none", lab, "fpr_ratio")
ATK = [s for s in T if s != "none"]
N["sg_max_aw"] = max(T[s]["Sangam (full)"]["attacker_weight"][0] for s in ATK)
N["flt_max_aw"] = max(T[s]["FLTrust"]["attacker_weight"][0] for s in ATK)
N["maj_flt"] = g(MAJ, "FLTrust", "tpr")
SW4 = next((r for r in SW if r["scenario"] == "none" and r["fair_max"] == 4.0), None)


def fall_txt(x):
    return "below 1%" if x < 0.01 else f"at most {100 * x:.0f}%"


def top_gainers(n=2):
    gains = sorted(((bs[b][0] - bl[b][0], BANKS[int(b)]) for b in bl), reverse=True)[:n]
    return " and ".join(f"the {name} (+{100 * gv:.0f} points)" for gv, name in gains)


def drop_txt(d):
    return "none" if d <= 0.005 else f"{100 * d:.0f} points"


def fmt_up(x):
    return f"+{100 * x:.0f}%"


# ------------------------------------------------------------------ shared CSS
BASE_CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
* { box-sizing: border-box; }
body { font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif; color: #15171b; font-size: 10pt; line-height: 1.5; margin: 0; }
h1 { font-size: 19pt; line-height: 1.2; letter-spacing: -.01em; margin: 0 0 6pt; }
h2 { font-size: 12.5pt; margin: 16pt 0 6pt; color: #0f1115; border-bottom: 1px solid #e4e3df; padding-bottom: 3pt; }
h3 { font-size: 10.5pt; margin: 10pt 0 4pt; }
p { margin: 0 0 7pt; text-align: justify; }
.authors { color: #4a4b50; margin-bottom: 10pt; }
.abstract { background: #f3f2ee; border-radius: 6pt; padding: 10pt 12pt; margin: 8pt 0 6pt; }
.abstract p { margin: 0; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 6pt 0 4pt; }
th, td { border-bottom: 1px solid #e4e3df; padding: 3.5pt 5pt; text-align: right; }
th:first-child, td:first-child { text-align: left; }
th { background: #f3f2ee; font-weight: 600; }
tr.ours td { background: #e6f0fc; font-weight: 600; }
.cap { font-size: 8.6pt; color: #4a4b50; margin: 2pt 0 10pt; }
figure { margin: 6pt 0 8pt; break-inside: avoid; }
figure img { width: 100%; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 10pt; }
.eq { font-family: 'Cambria Math', 'STIX Two Math', Georgia, serif; text-align: center; margin: 6pt 0; font-size: 10.5pt; }
.algo { border: 1px solid #d0cfca; border-radius: 6pt; padding: 8pt 10pt; font-size: 8.8pt; break-inside: avoid; }
.algo ol { margin: 4pt 0 0 14pt; padding: 0; }
ul { margin: 0 0 7pt 14pt; padding: 0; }
li { margin-bottom: 2pt; }
.refs li { font-size: 8.5pt; margin-bottom: 3pt; }
.tag { display: inline-block; background: #e6f0fc; color: #1c5cab; border-radius: 4pt; padding: 0 5pt; font-size: 8.5pt; font-weight: 600; }
"""
FONT = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">'

ORDER = ["Local only", "Centralised (pooled data)", "FedAvg", "Median", "Trimmed-Mean", "Multi-Krum", "FLTrust",
         "FedAvg + Fair", "Multi-Krum + Fair", "FLTrust + Fair", "Sangam-Trust (no fairness)", "Sangam (full)"]
SCN = {"none": "No attack", "label_flip": "Label flip, 2 banks", "sign_flip": "Model poisoning, 2 banks",
       "targeted_senior": "Senior-targeted, 2 banks", "label_flip_majority": "Label flip, 4 of 7",
       "sign_flip_majority": "Model poisoning, 4 of 7", "targeted_senior_majority": "Senior-targeted, 4 of 7"}


def robustness_table():
    scen = [s for s in SCN if s in T]
    meths = ["FedAvg", "Median", "Trimmed-Mean", "Multi-Krum", "FLTrust", "FedAvg + Fair", "FLTrust + Fair",
             "Sangam-Trust (no fairness)", "Sangam (full)"]
    h = "<table><tr><th>Method</th>" + "".join(f"<th>{SCN[s]}</th>" for s in scen) + "</tr>"
    for m in meths:
        cls = ' class="ours"' if m == "Sangam (full)" else ""
        h += f"<tr{cls}><td>{m}</td>" + "".join(
            f"<td>{100 * T[s][m]['tpr'][0]:.1f}</td>" if m in T[s] else "<td>–</td>" for s in scen) + "</tr>"
    return h + "</table>"


def clean_table():
    h = ("<table><tr><th>Method</th><th>AUC</th><th>Fraud caught (TPR)</th><th>Senior fraud caught</th>"
         "<th>FPR 50+</th><th>FPR &lt;50</th><th>FPR ratio</th></tr>")
    for m in ORDER:
        if m not in T["none"]:
            continue
        r = T["none"][m]
        cls = ' class="ours"' if m == "Sangam (full)" else ""
        h += (f"<tr{cls}><td>{m}</td><td>{r['auc'][0]:.3f}</td><td>{pm('none', m, 'tpr')}</td>"
              f"<td>{pm('none', m, 'tpr_senior')}</td><td>{p(r['fpr_senior'][0])}</td><td>{p(r['fpr_non_senior'][0])}</td>"
              f"<td>{r['fpr_ratio'][0]:.2f}</td></tr>")
    return h + "</table>"


def targeted_table():
    h = ("<table><tr><th>Method</th><th>Fraud caught</th><th>Senior fraud caught</th>"
         "<th>Attacker influence</th><th>FPR ratio</th></tr>")
    for m in ["FedAvg", "Median", "Trimmed-Mean", "Multi-Krum", "FLTrust", "FLTrust + Fair", "Sangam-Trust (no fairness)", "Sangam (full)"]:
        r = T[TG][m]
        cls = ' class="ours"' if m == "Sangam (full)" else ""
        aw = f"{100 * r['attacker_weight'][0]:.0f}%" if r["attacker_weight"] else "n/a"
        h += (f"<tr{cls}><td>{m}</td><td>{pm(TG, m, 'tpr')}</td><td>{pm(TG, m, 'tpr_senior')}</td>"
              f"<td>{aw}</td><td>{r['fpr_ratio'][0]:.2f}</td></tr>")
    return h + "</table>"


def bank_table():
    h = "<table><tr><th>Simulated bank</th><th>Applications (train)</th><th>Share aged 50+</th><th>Fraud rate</th><th>Alone</th><th>In Sangam</th></tr>"
    for i, b in enumerate(BANKSTATS):
        h += (f"<tr><td>{b['bank']}</td><td>{b['applications']:,}</td><td>{p(b['senior_share'], 0)}</td><td>{p(b['fraud_rate'], 2)}</td>"
              f"<td>{p(bl[str(i)][0])}</td><td>{p(bs[str(i)][0])}</td></tr>")
    return h + "</table>"


def sweep_table():
    rows = [r for r in SW if r["scenario"] == "none"]
    h = "<table><tr><th>λ<sub>max</sub></th><th>Fraud caught</th><th>Senior fraud caught</th><th>FPR 50+</th><th>FPR &lt;50</th><th>FPR ratio</th></tr>"
    for r in rows:
        h += (f"<tr><td>{r['fair_max']:g}{' (off)' if r['fair_max'] == 1 else ''}</td><td>{p(r['tpr'][0])}</td><td>{p(r['tpr_senior'][0])}</td>"
              f"<td>{p(r['fpr_senior'][0])}</td><td>{p(r['fpr_non_senior'][0])}</td><td>{r['fpr_ratio'][0]:.2f}</td></tr>")
    return h + "</table>"


def alignment_para():
    def get(sc, al):
        return next((r for r in AB if r["scenario"] == sc and r["align"] == al), None)
    rows = [(sc, get(sc, True), get(sc, False)) for sc in ("sign_flip", "sign_flip_majority")]
    if not all(a and b for _, a, b in rows):
        return ""
    lab = {"sign_flip": "2 poisoning banks", "sign_flip_majority": "4 of 7 poisoning banks"}
    tbl = "<table><tr><th>Scenario</th><th>Trust scored on</th><th>Fraud caught</th><th>Attacker influence</th></tr>"
    for sc, a, b in rows:
        for r, name in ((b, "unweighted loss (naive)"), (a, "fairness-weighted loss (Sangam)")):
            cls = ' class="ours"' if r is a else ""
            tbl += f"<tr{cls}><td>{lab[sc]}</td><td>{name}</td><td>{p(r['tpr'][0])}</td><td>{p(r['attacker_weight'][0])}</td></tr>"
    tbl += "</table>"
    return ("<p><b>Why alignment matters.</b> Our first prototype scored updates on the unweighted loss. Once the fairness "
            "controller raises λ, honest updates push senior scores down, which can look harmful on the unweighted loss. "
            "In the final design (with clipping and the harm check) the effect is small but measurable. Unaligned scoring leaks some "
            "influence to attackers, while aligned scoring keeps it near zero (model poisoning, 3 seeds):</p>" + tbl + '<div class="cap"><b>Table 2a.</b> Ablation of trust-objective alignment.</div>')


def report_html():
    k = TEAM["members"][1]
    kinst = k["institution"] if k["institution"] != "TO_FILL" else "[institution]"
    authors = f"Yash Goyal (IIT Gandhinagar) · {k['name']} ({kinst})"
    fig = lambda n: f"../site/figures/{n}.png"
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONT}<style>{BASE_CSS}</style><title>Sangam technical report</title></head><body>
<h1>Sangam: Fair and Poisoning-Resilient Federated Learning for Cross-Bank Detection of Mule-Account Openings</h1>
<div class="authors">{authors} · GIFT FutureLab Grand Challenge 2026–27 · Technical report, November 2026</div>
<div class="abstract"><p><b>Abstract.</b> Mule accounts are the plumbing of digital fraud, and they are opened one bank at a time. No single bank sees the whole pattern, small banks have too few fraud examples to learn from, and data-protection law rightly prevents pooling customer records. Federated learning lets banks train one model without moving data, but naïve federation has two failure modes that block deployment between institutions: one compromised participant can poison the shared model, and the model can encode systematic unfairness, here flagging genuine applicants aged 50+ <b>{N['fed_mult']:.1f}×</b> as often as younger applicants. We present <b>Sangam</b>, a consortium protocol with two additions to federated averaging: (i) a <i>segment-level trust check</i> that test-applies each bank's update to a small operator-held reference set and gives zero weight to any update that harms some customer segment, and (ii) a <i>fairness controller</i> that adaptively reweights genuine applicants of the over-flagged group, extending our DCA-FW method to predictive equality. On the one-million-application Bank Account Fraud benchmark (NeurIPS 2022), split across seven simulated Indian banks, Sangam catches <b>{fmt_up(N['up_sg'])}</b> more fraudulent account openings than banks working alone. It cuts the false-alarm rate for genuine seniors from {p(N['fed_fs'])} to {p(N['sg_fs'])}, while younger applicants' rate rises from {p(N['fed_fn'])} to {p(N['sg_fn'])} (fairness ratio {N['fed_ratio']:.2f} → {N['sg_ratio']:.2f}), and still catches {p(N['maj_sg'])} of fraud when <b>4 of 7 banks are compromised</b>, where FedAvg, Median, Trimmed-Mean and Multi-Krum catch {fall_txt(N['maj_best_dist'])}. Against a stealthy attack that targets only senior citizens' fraud, Sangam gives compromised banks {p(N['tg_sg_aw'], 0)} of the influence (FLTrust: {p(N['tg_flt_aw'], 0)}) and keeps its fairness ratio ({N['clean_sg_ratio']:.2f} → {N['tg_sg_ratio']:.2f}). FLTrust combined with our fairness controller falls to {N['tg_fltf_ratio']:.2f}. Across all six attack scenarios Sangam never gives attackers more than {p(N['sg_max_aw'], 0)} of the influence.</p></div>

<h2>1. Problem and motivation</h2>
<p>Indian banks reported frauds involving ₹36,014 crore in FY 2024-25 [1]. Most digital frauds cash out through <i>mule accounts</i>: accounts opened with stolen, rented or synthetic identities. The RBI Innovation Hub's MuleHunter.AI now flags roughly 20,000 suspected mule accounts a month [2], which shows that machine learning works for this task. Each bank, however, still models only its own customers, while fraud rings spread accounts across banks. Pooling data is not an option: the DPDP Rules 2025 [3] and banking secrecy limit what can be shared. Federated learning (FL) is the natural fit, and SWIFT has piloted it with major international banks for cross-border payment fraud [4].</p>
<p>Two obstacles keep FL from deployment in a consortium of competitors. <b>Trust:</b> a single compromised or malicious member can poison the shared model. Standard Byzantine-robust aggregators (Krum, Median, Trimmed-Mean) assume a minority of attackers and rely on agreement between clients. <b>Fairness:</b> fraud models learn from base rates. In the benchmark used here, applicants aged 50+ have several times the fraud rate of younger ones, so a standard model wrongly flags genuine seniors far more often. Wrongful flags at account opening mean delayed or denied accounts for precisely the customers that financial-inclusion policy targets, and regulators are already acting against blanket freezes of innocent customers' accounts [5]. Robust aggregation and fairness are also known to be in tension: robust rules can treat honest but different clients as outliers [6].</p>
<p><b>Contributions.</b> (1) A consortium protocol, Sangam, that combines federated training, a segment-level trust check and a fairness controller. (2) A segment-targeted threat model (poisoning only senior citizens' fraud labels), and evidence that agreement-based and cosine-based defences admit it while a per-segment check does not. (3) An open benchmark: seven simulated banks, twelve methods, seven attack scenarios and three seeds on BAF, with code and an interactive simulator.</p>

<h2>2. Setting and threat model</h2>
<p><b>Consortium.</b> <i>K</i> = 7 banks with different customer mixes (Table 1) train a shared fraud classifier for account-opening applications. A neutral <i>operator</i>, for example a regulator sandbox or an industry hub, runs aggregation and holds a small labelled reference ("probe") set <i>P</i>: 2% of the training period, never used for client training. In practice this could be a pooled set of confirmed fraud cases already shared with authorities, or synthetic data.</p>
<p><b>Adversary.</b> A subset of banks is compromised: two banks (about 33% of data) or four of seven (about 59%, beyond the tolerance of distance-based defences). Attacks: <i>label flip</i> (all labels inverted), <i>model poisoning</i> (update sent as −4× the honest update), and <i>senior-targeted</i> poisoning (only fraud cases of applicants aged 50+ are relabelled genuine and up-weighted 5×). The senior-targeted attack is stealthy because the majority segment is unaffected, which mirrors the targeting of elderly people's identities in real fraud.</p>
<p><b>Protected group.</b> Following the BAF protocol [7], the protected attribute is age ≥ 50 and fairness is <i>predictive equality</i>: the ratio of false-positive rates between groups at the operating point (1.0 = equal).</p>

<h2>3. Method</h2>
<p><b>Local training.</b> In round <i>t</i> each bank <i>k</i> starts from global weights <i>w<sub>t</sub></i> and runs one epoch of Adam on a weighted cross-entropy. Fraud cases have weight <i>π</i> = 10. Genuine applicants in group <i>g</i> have weight <i>λ<sub>g</sub></i>, broadcast by the operator. The bank returns Δ<sub>k</sub> = <i>w<sub>k</sub></i> − <i>w<sub>t</sub></i>. Raw data never leaves the bank.</p>
<p><b>Segment-level trust.</b> Updates are clipped to the median update norm, Δ̃<sub>k</sub> = Δ<sub>k</sub>·min(1, <i>c</i>/‖Δ<sub>k</sub>‖), so a boosted update cannot dominate. For each customer segment <i>g</i> the operator computes the relative change in the <i>λ-weighted</i> loss on the probe set:</p>
<div class="eq">ι<sub>k,g</sub> = [ L<sub>g</sub>(w<sub>t</sub>) − L<sub>g</sub>(w<sub>t</sub> + Δ̃<sub>k</sub>) ] / L<sub>g</sub>(w<sub>t</sub>)</div>
<div class="eq">s<sub>k</sub> = 0 if min<sub>g</sub> ι<sub>k,g</sub> &lt; −δ,&nbsp;&nbsp; otherwise max(0, max<sub>g</sub> ι<sub>k,g</sub> + τ)</div>
<p>The aggregate is <i>w</i><sub>t+1</sub> = <i>w<sub>t</sub></i> + Σ<sub>k</sub> α<sub>k</sub>Δ̃<sub>k</sub> with α<sub>k</sub> ∝ <i>s<sub>k</sub> n<sub>k</sub></i>. An update that harms any segment by more than δ = 5% is rejected, which catches poison hidden in a minority segment. An update that helps <i>some</i> segment is kept even if it barely moves the majority. Because trust is anchored in the probe set rather than in agreement between clients, the check still works when most participants are compromised, as FLTrust [8] showed for cosine-based scoring. Our score differs from FLTrust by evaluating each segment separately and by scoring on the fairness-weighted objective.</p>
<p><b>Fairness controller (DCA-FW for predictive equality).</b> After aggregation the operator scores the probe set, sets the threshold at 5% FPR and measures each group's false-positive rate <i>f<sub>g</sub></i>. It then raises the weight of genuine applicants in the over-flagged group multiplicatively: <i>λ<sub>g</sub></i> ← clip(<i>λ<sub>g</sub></i>·exp(η·log(<i>f<sub>g</sub></i>/<i>f<sub>ḡ</sub></i>)), 1, λ<sub>max</sub>), with η = 0.5 and λ<sub>max</sub> = 6. This extends our Dynamic Client-Adaptive Fairness Weighting (DCA-FW), developed for demographic fairness in federated image classification, to false-positive parity in fraud detection.</p>
{alignment_para()}

<h2>4. Experimental setup</h2>
<p><b>Data.</b> BAF Base [7]: 1,000,000 bank-account-opening applications (1.10% fraud), a privacy-preserving synthetic dataset that Feedzai generated from a real-world account-opening fraud dataset, with 31 features. Train on months 0–5, test on months 6–7 (205,011 applications). <b>Banks.</b> Each applicant is assigned to one of seven archetypal banks by a feature-dependent random rule. For example, the Regional Rural Bank and the Urban Co-operative Bank mostly serve older and lower-income customers, and the Digital Neobank serves younger ones. This yields strongly non-IID members (Table 1). <b>Model.</b> MLP with layers 51→128→64→1, 30 rounds, 1 local epoch, batch 1024, learning rate 10<sup>−3</sup>. <b>Baselines.</b> Bank-alone training (same compute), centralised training on pooled data (an upper bound that is not legally possible in practice), FedAvg, coordinate-wise Median, Trimmed-Mean (β = 2), Multi-Krum (f = 2) and FLTrust (server update computed on the same probe set), each with and without our fairness controller. <b>Metrics.</b> AUC; TPR at 5% FPR (the BAF operating point); TPR on the senior group; per-group FPR; FPR ratio; and the attacker influence (the mean share of aggregation weight given to compromised banks). Three seeds; each re-draws bank membership, probe set and initialisation.</p>
{bank_table()}
<div class="cap"><b>Table 1.</b> Simulated consortium (seed 0) and fraud caught at each bank's own 5% FPR: training alone vs inside Sangam (mean over 3 seeds).</div>

<h2>5. Results</h2>
<h3>5.1 Collaboration pays off for every bank</h3>
<p>Federation lifts fraud capture from {p(N['loc'])} (banks alone) to {p(N['fed'])} with FedAvg, matching centralised training on pooled data ({p(N['cen'])}) without moving any record. With its fairness controller on, Sangam catches {p(N['sg'])}, which is <b>{fmt_up(N['up_sg'])}</b> over banks working alone. Every one of the seven banks improves, by {100*N['bank_up_min']:.0f} to {100*N['bank_up_max']:.0f} percentage points (Table 1, Figure 1). The largest gains go to {top_gainers()}. The senior-heavy rural and co-operative banks gain least, because their local data already contains a relatively high share of fraud cases.</p>
<div class="two"><figure><img src="{fig('bank_uplift')}"><div class="cap"><b>Figure 1.</b> Fraud caught per bank, alone vs Sangam.</div></figure>
<figure><img src="{fig('fairness')}"><div class="cap"><b>Figure 2.</b> Genuine applicants wrongly flagged, by age group.</div></figure></div>
<h3>5.2 Fairness</h3>
<p>Standard federated training wrongly flags {p(N['fed_fs'])} of genuine seniors against {p(N['fed_fn'])} of younger applicants (ratio {N['fed_ratio']:.2f}). Sangam brings this to {p(N['sg_fs'])} vs {p(N['sg_fn'])} (ratio {N['sg_ratio']:.2f}): about <b>{N['seniors_saved_per_lakh']:,.0f} fewer wrongly flagged for every lakh genuine senior applicants</b>. Because the overall alert budget stays at 5%, younger applicants' false-alarm rate rises from {p(N['fed_fn'])} to {p(N['sg_fn'])}, so the burden is shared more evenly. With λ<sub>max</sub> = 6 the controller slightly over-corrects. The fairness price is fraud capture ({p(N['sgt'])} → {p(N['sg'])}). The operator chooses the operating point with λ<sub>max</sub> (Table 4b). In our sweep, λ<sub>max</sub> = 4 reaches a ratio of {SW4['fpr_ratio'][0]:.2f} at {p(SW4['tpr'][0])} fraud caught. This sweep was evaluated on the test months; a deployment would choose λ<sub>max</sub> on a validation period.</p>
{clean_table()}
<div class="cap"><b>Table 2.</b> No attack. Mean ± std over 3 seeds.</div>
<h3>5.3 Robustness to compromised banks</h3>
<p>Table 3 reports fraud caught under every scenario. Distance- and median-based rules hold against a minority of attackers but <b>collapse when four of seven banks are compromised</b> (FedAvg, Median, Trimmed-Mean and Multi-Krum all catch {fall_txt(N['maj_best_dist'])}). Probe-anchored methods, FLTrust ({p(N['maj_flt'])}) and Sangam ({p(N['maj_sg'])}), survive every scenario, and on these attacks the two are comparable. Adding our fairness controller to FedAvg or Multi-Krum makes them fair but not robust: FedAvg + Fair collapses under model poisoning.</p>
{robustness_table()}
<div class="cap"><b>Table 3.</b> Fraud caught (%) at 5% FPR, mean of 3 seeds.</div>
<h3>5.4 Senior-targeted poisoning</h3>
<p>This is the scenario that separates Sangam from FLTrust. Four banks quietly relabel only senior citizens' fraud as genuine. <b>Without the fairness controller</b>, we compare each defence with its own no-attack run. FedAvg loses {100*N['tg_fed_drop']:.0f} points of senior fraud capture. Multi-Krum loses {100*N['tg_krum_drop']:.0f} points because it selects the mutually consistent attackers. FLTrust's cosine score sees updates that point roughly the right way for the majority, gives the attackers {p(N['tg_flt_aw'], 0)} of the influence and loses {100*N['tg_flt_drop']:.0f} points (with large variation across seeds). Sangam's per-segment check sees the senior-segment loss rise, gives the attackers {p(N['tg_sgt_aw'], 0)} and loses {100*N['tg_sgt_drop']:.0f} points. <b>With the fairness controller</b>, the attack shows up as lost fairness instead. FLTrust + Fair falls from a fairness ratio of {N['clean_fltf_ratio']:.2f} to {N['tg_fltf_ratio']:.2f} and gives attackers {p(N['tg_fltf_aw'], 0)} of the influence, while Sangam stays at {N['tg_sg_ratio']:.2f} (from {N['clean_sg_ratio']:.2f}) and gives them {p(N['tg_sg_aw'], 0)}. Across all six attack scenarios Sangam never gives attackers more than {p(N['sg_max_aw'], 0)} of the influence; FLTrust gives up to {p(N['flt_max_aw'], 0)}.</p>
<figure><img src="{fig('targeted')}"><div class="cap"><b>Figure 3.</b> Senior-targeted poisoning by 4 of 7 banks. Left: senior fraud capture lost to the attack, for defences without the fairness controller. Right: fairness ratio before and after the attack, for defences with it, and the influence given to attackers.</div></figure>
{targeted_table()}
<div class="cap"><b>Table 4a.</b> Senior-targeted poisoning, 4 of 7 banks. Mean ± std over 3 seeds.</div>
<h3>5.5 Fairness–capture trade-off</h3>
{sweep_table()}
<div class="cap"><b>Table 4b.</b> Sangam with different caps on the fairness weights (no attack, mean of 3 seeds).</div>

<h2>6. Deployment at GIFT City</h2>
<p><b>Architecture.</b> Sangam runs as a scoring service at account opening. Each member bank hosts a training agent inside its own environment. The operator hosts aggregation, the probe set and the audit log. <b>Regulatory path.</b> IFSCA's FinTech Sandbox Framework (March 2026) [9] provides an innovation sandbox for testing on data and a regulatory sandbox for live testing. We propose (i) replay on historical data from 2–3 IFSC Banking Units, (ii) shadow mode alongside existing checks, then (iii) a live sandbox test. An IFSCA survey (July 2026) reports that AI adoption among IFSC entities is strongest in risk and compliance, including AML-CFT, KYC and fraud detection [10]. <b>Governance.</b> The per-round trust scores and fairness gap form an audit trail for supervisors. They also provide a contribution measure for sharing consortium costs and rewards among members.</p>

<h2>7. Limitations and next steps</h2>
<ul>
<li>BAF covers account <i>openings</i>, is privacy-preserved synthetic-from-real data, and is not Indian. Bank membership is simulated. Validation on Indian data via a sandbox is the next step.</li>
<li>The harm check can temporarily give zero weight to an <i>honest</i> bank whose customers differ sharply from one segment. In the senior-targeted run, for example, the Digital Neobank (almost no customers aged 50+) is excluded in some rounds. A softer, per-segment-capped penalty is future work.</li>
<li>The trust check needs a small labelled reference set at a neutral operator, and the operator sees individual updates. We plan to run scoring inside a trusted execution environment and to add client-level differential privacy.</li>
<li>We study one protected attribute (age ≥ 50) and a two-group fairness notion; extending the segment check to intersecting groups (age × income × region) is straightforward but untested.</li>
<li>Adaptive attackers who know the probe-set distribution, and graph-based mule-ring features across banks, are open directions.</li>
</ul>

<h2>References</h2>
<ol class="refs">
<li>RBI Annual Report 2024-25, reported in Business Standard, 29 May 2025.</li>
<li>"AI-enabled tool MuleHunter detecting 20,000 mule accounts every month: RBI Governor", Free Press Journal, Nov 2025.</li>
<li>Digital Personal Data Protection Rules, 2025 (MeitY, notified 13–14 Nov 2025).</li>
<li>SWIFT, "Swift to launch AI-powered fraud defence to enhance cross-border payments", press release, 2024.</li>
<li>RBI draft directions to standardise account blocking in cyber-fraud cases, reported by Inc42, 2026.</li>
<li>"On the hidden costs of fairness in Byzantine-robust decentralized federated learning" (NC A&amp;T State University).</li>
<li>S. Jesus et al., "Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for ML Evaluation", NeurIPS 2022 Datasets &amp; Benchmarks.</li>
<li>X. Cao, M. Fang, J. Liu, N. Gong, "FLTrust: Byzantine-robust Federated Learning via Trust Bootstrapping", NDSS 2021.</li>
<li>IFSCA FinTech Sandbox Framework, circular of 16 March 2026.</li>
<li>IFSCA survey on AI adoption among IFSC entities, July 2026, as summarised in law-firm newsletters.</li>
<li>P. Blanchard et al., "Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent" (Krum), NeurIPS 2017; D. Yin et al., "Byzantine-Robust Distributed Learning" (Median / Trimmed-Mean), ICML 2018.</li>
<li>B. McMahan et al., "Communication-Efficient Learning of Deep Networks from Decentralized Data" (FedAvg), AISTATS 2017.</li>
</ol>
</body></html>"""


def team_html():
    rows = "".join(
        f"""<div class="m"><h2>{i + 1}. {m['name']} <span class="tag">{m['role']}</span></h2>
<table><tr><th>Full name</th><td>{m['name']}</td></tr><tr><th>Email address</th><td>{m['email']}</td></tr>
<tr><th>Institution</th><td>{m['institution']}</td></tr><tr><th>Role / programme of study</th><td>{m['programme']}</td></tr>
<tr><th>Contribution to the proposed work</th><td>{m['contribution']}</td></tr></table></div>"""
        for i, m in enumerate(TEAM["members"]))
    css = BASE_CSS + "table th{width:32%;text-align:left;vertical-align:top} table td{text-align:left} .m{margin-bottom:14pt}"
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONT}<style>{css}</style><title>Team details</title></head><body>
<h1>Team details: {TEAM['team_name']}</h1>
<div class="authors">GIFT FutureLab Grand Challenge 2026–27 · Project: Sangam, fair and attack-resilient federated AI that lets banks jointly stop mule accounts without sharing customer data</div>
{rows}</body></html>"""


def pdf(html_path: Path, out: Path):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                    f"--print-to-pdf={out}", html_path.as_uri()], check=True, capture_output=True)
    print("wrote", out)


if __name__ == "__main__":
    (DOCS / "report.html").write_text(report_html())
    (DOCS / "team_details.html").write_text(team_html())
    pdf(DOCS / "report.html", SITE / "Sangam_Technical_Report.pdf")
    pdf(DOCS / "team_details.html", DOCS / "Sangam_Team_Details.pdf")
    subprocess.run([sys.executable, str(DOCS / "build_deck.py")], check=True)
    subprocess.run([sys.executable, str(DOCS / "build_form.py")], check=True)
