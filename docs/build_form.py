"""Generate copy-paste answers for the GIFT FutureLab application form, with word counts.
Numbers come from results/summary.json via build_docs.N."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs"))
from build_docs import N, TEAM, p, fmt_up, fall_txt  # noqa: E402

SITE_URL = (ROOT / "docs" / "site_url.txt").read_text().strip() if (ROOT / "docs" / "site_url.txt").exists() else "https://<your-github-username>.github.io/sangam/"

TITLE = "Sangam: fair, attack-resilient federated AI that lets banks jointly stop mule accounts without sharing customer data"

Q_DESCRIBE = f"""Sangam lets several banks train one shared AI model to detect fraudulent account openings, the usual origin of mule accounts, without any customer record leaving any bank. Each bank trains the model on its own data and sends back only a model update. A neutral operator, such as a regulator sandbox or industry hub, combines them.

Plain federated learning is not safe enough between competitors, so Sangam adds two safeguards. First, a segment-level trust check: the operator test-applies each update to a small reference dataset and measures its effect on every customer segment separately (for example, applicants aged 50+ and under 50). Any update that harms a segment gets zero weight. This blocks poisoned updates, including stealthy attacks hidden inside one segment, and keeps working even when most participants are compromised. Second, a fairness controller, extended from our DCA-FW fairness research, that measures false-alarm rates for each age group and re-weights training so that genuine senior citizens are not flagged more often than younger customers.

We built a working prototype in Python and PyTorch and benchmarked it on the public Bank Account Fraud dataset (1 million applications, NeurIPS 2022). We split the data across seven simulated Indian banks and compared Sangam with 11 other methods under seven attack scenarios. Sangam catches {fmt_up(N['up_sg'])} more fraud than banks working alone and evens out false alarms (genuine seniors {p(N['fed_fs'])} → {p(N['sg_fs'])}; under-50s {p(N['fed_fn'])} → {p(N['sg_fn'])}). With 4 of 7 banks compromised it still catches {p(N['maj_sg'], 0)} of fraud, while standard methods collapse."""

Q_PROBLEM = f"""Mule accounts, opened with stolen, rented or synthetic identities, are how fraud money moves. Indian banks reported frauds involving ₹36,014 crore in FY 2024-25, and RBI's MuleHunter.AI flags around 20,000 suspected mule accounts a month. Fraud rings spread their accounts across many banks, but each bank models only its own customers. Smaller lenders such as regional rural, co-operative and small finance banks see too few fraud cases to train strong models. The DPDP Rules 2025 and banking secrecy rightly prevent pooling customer data.

Collaborating without sharing data (federated learning) is possible, but two problems block it in practice. The first is trust: one compromised participant can poison the shared model for everyone. The second is fairness: on the benchmark we use, a standard model wrongly flags genuine applicants aged 50+ {N['fed_mult']:.1f} times as often as younger ones. These wrongful flags delay or deny accounts for exactly the customers that financial inclusion is meant to serve.

The problem is felt by banks and IFSC Banking Units (fraud losses and compliance cost), by regulators (systemic fraud), and by customers, both fraud victims and genuine applicants who are wrongly blocked."""

Q_APPLY = f"""Use case: shared risk scoring at account opening across a consortium of banks, starting with IFSC Banking Units at GIFT City and extending to onshore banks.

How it works in practice:
1. Each member bank runs a Sangam training agent inside its own environment, connected to its onboarding and KYC data. Customer data never leaves the bank.
2. A neutral operator (for example within IFSCA's sandbox, or an industry utility) runs aggregation, holds a small labelled reference set (such as confirmed fraud cases already reported to authorities) and keeps the audit log.
3. Each round, banks send model updates. The operator applies the segment-level trust check and the fairness controller, then returns the improved model.
4. Each bank scores new applications with the shared model as one extra signal in its existing onboarding checks. High-risk applications go to enhanced due diligence by the bank's own team; no decision is automated.
5. Every round's trust scores and fairness gap give supervisors an audit trail, and give members a basis for sharing costs fairly.

Rollout: replay on historical data from 2–3 IBUs in IFSCA's innovation sandbox, then shadow mode alongside existing checks, then a live regulatory-sandbox test.

The same protocol extends to transaction monitoring, UPI mule-account detection and cross-border payment fraud."""

Q_NOVEL = f"""Closest alternatives and what Sangam adds:

1. Single-bank models (today's norm, including MuleHunter.AI-style deployments) learn only from one bank's customers. Sangam learns across banks without sharing data: {fmt_up(N['up_sg'])} more fraud caught on our benchmark.
2. Standard federated learning (FedAvg) can be poisoned by one participant and has no fairness control.
3. Byzantine-robust aggregation (Krum, Median, Trimmed-Mean) relies on agreement between participants. With 4 of 7 banks compromised these methods caught {fall_txt(N['maj_best_dist'])} of fraud; Sangam caught {p(N['maj_sg'], 0)}.
4. FLTrust (NDSS 2021) also anchors trust in reference data, but it judges each update as a whole. Under poisoning aimed only at senior citizens' fraud, it gave attackers {p(N['tg_flt_aw'], 0)} of the influence. Combined with our fairness controller, its fairness ratio collapsed from {N['clean_fltf_ratio']:.2f} to {N['tg_fltf_ratio']:.2f}. Sangam scores every customer segment separately: attackers got {p(N['tg_sg_aw'], 0)} of the influence and fairness held ({N['tg_sg_ratio']:.2f}). Across six attack scenarios, Sangam never gave attackers more than {p(N['sg_max_aw'], 0)} of the influence.

Our fairness controller extends the team lead's DCA-FW research to false-alarm parity. We know of no published system that combines all three properties for bank fraud."""

Q_NEXT = """1. Real-data validation: apply to IFSCA's innovation sandbox and replay Sangam on historical onboarding data from 2–3 IFSC Banking Units.
2. Operator and reference data: agree a neutral operator and a small shared reference set, such as confirmed fraud cases already reported to authorities.
3. Privacy hardening: run update scoring inside a trusted execution environment and add client-level differential privacy.
4. Product: integrate a scoring API into onboarding and KYC workflows, extend the system to transaction-level mule detection, and add cross-bank graph features.
5. User validation and regulatory assessment: run workshops with bank fraud teams, review the design against DPDP and IFSCA requirements, then shadow-mode testing and a live sandbox pilot."""

Q_OTHER = f"""All code, experiment logs and an interactive consortium simulator are public at the link above. The full benchmark (216 federated training runs) is reproducible in about 30 minutes on a laptop. Sangam's fairness controller extends the team lead's earlier research on Dynamic Client-Adaptive Fairness Weighting (DCA-FW) in federated learning, done at IIT Gandhinagar. Bank names in our benchmark are generic archetypes; the data is the public Feedzai BAF dataset, not Indian bank data. A pilot on Indian data is our next step."""


def wc(s):
    return len(re.findall(r"[\w₹+%.,'’()\-–/]+", s))


def main():
    t = TEAM
    k = t["members"][1]
    blocks = [
        ("Name of applicant / team lead", "Yash Goyal", None),
        ("Email address", t["members"][0]["email"], None),
        ("Mobile number", "(your number)", None),
        ("Institution / organisation name", "Indian Institute of Technology Gandhinagar", None),
        ("Current role", "Undergraduate student", None),
        ("City and state", "Gandhinagar, Gujarat", None),
        ("Team name", t["team_name"], None),
        ("Total number of team members, including the team lead", str(len(t["members"])), None),
        ("Details of other team members (file upload)", "Upload docs/Sangam_Team_Details.pdf", None),
        ("Title of the technology / research / innovation", TITLE, None),
        ("Which area best describes your work?", "Cybersecurity, fraud prevention and risk management", None),
        ("Briefly describe your technology, research or innovation (limit 250 words)", Q_DESCRIBE, 250),
        ("What problem or opportunity in the financial sector does your work address? (suggested 200)", Q_PROBLEM, 200),
        ("How can your work be applied to this problem or opportunity? (suggested 250)", Q_APPLY, 250),
        ("What is novel or distinctive about your work? (suggested 200)", Q_NOVEL, 200),
        ("Who could potentially use or benefit from your work?", "Tick: Banks or other financial institutions · Financial technology companies · Regulators or supervisory bodies · Individual consumers", None),
        ("What is the current stage of your work?", "Prototype developed or tested", None),
        ("Has your work been tested or validated in a financial-sector setting?", "No (tested on a public benchmark dataset only)", None),
        ("What are the next steps required to develop or apply your work? (suggested 150)", Q_NEXT, 150),
        ("Link to a demonstration, publication or other supporting material", SITE_URL, None),
        ("How did you hear about the Grand Challenge?", "IIT Gandhinagar / IIEC (or whichever is true for you)", None),
        ("Applicant declaration / Consent", "Read and tick these yourself", None),
        ("Any other information you would like to share?", Q_OTHER, None),
    ]
    out = ["# GIFT FutureLab application: copy-paste answers", "",
           "Generated from the experiment results. Word counts are checked against the form's limits.", ""]
    ok = True
    for q, a, lim in blocks:
        n = wc(a)
        flag = ""
        if lim:
            flag = f"  _({n} words / limit {lim})_" + (" **OVER LIMIT**" if n > lim else " ✓")
            ok &= n <= lim
        out += [f"### {q}{flag}", "", a, ""]
    if "TO_FILL" in str(k):
        out.insert(3, f"> ⚠️ Kshitish's email, institution and programme are still TO_FILL in docs/team.json. Fill them in and rebuild before uploading the team PDF.\n")
    (ROOT / "FORM_ANSWERS.md").write_text("\n".join(out))
    for q, a, lim in blocks:
        if lim:
            print(f"{wc(a):4d}/{lim}  {q[:60]}")
    print("all within limits" if ok else "SOME ANSWERS OVER LIMIT")


def readme():
    r = f"""# Sangam: fair, attack-resilient federated learning against mule accounts

**Banks stop mule accounts together, without sharing a single customer record.**

Live site and interactive simulator: {SITE_URL}
Technical report: [site/Sangam_Technical_Report.pdf](site/Sangam_Technical_Report.pdf) · Pitch deck: [site/Sangam_Pitch_Deck.pdf](site/Sangam_Pitch_Deck.pdf)

Built for the GIFT FutureLab Grand Challenge 2026–27 (IIT Gandhinagar and GIFT City).

## What it does
Sangam is a federated learning protocol for a consortium of banks that detects fraudulent bank-account openings, the usual origin of mule accounts. Each bank trains on its own data; only model updates travel. On top of federated averaging it adds:

1. **Segment-level trust check**: the operator test-applies each bank's update to a small reference set and scores its effect on every customer segment separately. Updates that harm any segment get zero weight, which blocks poisoning (including poisoning hidden inside one segment) even when most participants are compromised.
2. **Fairness controller** (an extension of DCA-FW to predictive equality): it measures false-positive rates for applicants aged 50+ vs under 50 and reweights genuine applicants of the over-flagged group.

## Headline results (BAF Base, 1M applications, 7 simulated banks, 3 seeds)
| | Value |
|---|---|
| Fraud caught at 5% FPR: banks alone → Sangam | {p(N['loc'])} → {p(N['sg'])} ({fmt_up(N['up_sg'])}) |
| Genuine seniors wrongly flagged: FedAvg → Sangam | {p(N['fed_fs'])} → {p(N['sg_fs'])} (fairness ratio {N['fed_ratio']:.2f} → {N['sg_ratio']:.2f}) |
| Fraud caught with 4 of 7 banks poisoning (model poisoning) | Sangam {p(N['maj_sg'])}; FedAvg, Median, Trimmed-Mean, Krum: {fall_txt(N['maj_best_dist'])} |
| Attacker influence under senior-targeted poisoning (4 of 7) | Sangam {p(N['tg_sg_aw'], 0)} vs FLTrust {p(N['tg_flt_aw'], 0)} |

Full tables: [results/summary.md](results/summary.md).

## Reproduce
```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python -c "import kagglehub; print(kagglehub.dataset_download('sgpjesus/bank-account-fraud-dataset-neurips-2022'))"
# convert Base.csv to ../data/base.parquet (see experiments/prepare_data.py)
python experiments/prepare_data.py --csv <path-to>/Base.csv
python experiments/run_all.py --seeds 0 1 2      # 216 runs, about 30 min on a laptop
python experiments/sweep_fairness.py
python experiments/summarize.py
python docs/build_docs.py                         # report, deck, team sheet (needs Google Chrome)
python experiments/demo_live.py --attack targeted_senior --majority   # live demo
```

## Layout
- `src/sangam/data.py`: BAF loading, preprocessing, non-IID assignment to 7 archetypal banks
- `src/sangam/fl.py`: local training, attacks, FedAvg / Median / Trimmed-Mean / Multi-Krum / FLTrust / **Sangam** aggregators, fairness controller, metrics
- `experiments/`: benchmark runner, fairness sweep, summariser, live demo
- `site/`: project website with the interactive consortium simulator (deployed with GitHub Pages)
- `docs/`: generators for the report, deck and team sheet

## Honest limitations
BAF is privacy-preserved synthetic-from-real data about account openings, not Indian data, and bank membership is simulated. The trust check assumes a neutral operator with a small labelled reference set, and that operator sees individual updates. Fairness costs some fraud capture, a trade-off the operator tunes. See section 7 of the report.

Dataset: S. Jesus et al., *Turning the Tables*, NeurIPS 2022 Datasets & Benchmarks (Feedzai). Bank names are generic archetypes.
"""
    (ROOT / "README.md").write_text(r)


if __name__ == "__main__":
    main()
    readme()
