# Sangam: fair, attack-resilient federated learning against mule accounts

**Banks stop mule accounts together, without sharing a single customer record.**

Live site and interactive simulator: https://yashg1836.github.io/sangam/
Technical report: [site/Sangam_Technical_Report.pdf](site/Sangam_Technical_Report.pdf) · Pitch deck: [site/Sangam_Pitch_Deck.pdf](site/Sangam_Pitch_Deck.pdf)

Built for the GIFT FutureLab Grand Challenge 2026–27 (IIT Gandhinagar and GIFT City).

## What it does
Sangam is a federated learning protocol for a consortium of banks that detects fraudulent bank-account openings, the usual origin of mule accounts. Each bank trains on its own data; only model updates travel. On top of federated averaging it adds:

1. **Segment-level trust check**: the operator test-applies each bank's update to a small reference set and scores its effect on every customer segment separately. Updates that harm any segment get zero weight, which blocks poisoning (including poisoning hidden inside one segment) even when most participants are compromised.
2. **Fairness controller** (an extension of DCA-FW to predictive equality): it measures false-positive rates for applicants aged 50+ vs under 50 and reweights genuine applicants of the over-flagged group.

## Headline results (BAF Base, 1M applications, 7 simulated banks, 3 seeds)
| | Value |
|---|---|
| Fraud caught at 5% FPR: banks alone → Sangam | 39.6% → 47.2% (+19%) |
| Genuine seniors wrongly flagged: FedAvg → Sangam | 11.2% → 4.2% (fairness ratio 0.34 → 0.81) |
| Fraud caught with 4 of 7 banks poisoning (model poisoning) | Sangam 45.1%; FedAvg, Median, Trimmed-Mean, Krum: below 1% |
| Attacker influence under senior-targeted poisoning (4 of 7) | Sangam 2% vs FLTrust 34% |

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
