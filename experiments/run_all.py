"""Run the full Sangam benchmark: every method x attack scenario x seed.

Usage:  python experiments/run_all.py --data ../data/base.parquet --seeds 0 1 2 --workers 8
Writes results/runs.jsonl (one JSON line per run) and results/models/*.pt for the demo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

METHODS = [  # (label, method, fair)
    ("Local only", "local", False),
    ("Centralised (pooled data)", "central", False),
    ("FedAvg", "fedavg", False),
    ("Median", "median", False),
    ("Trimmed-Mean", "trimmed_mean", False),
    ("Multi-Krum", "multikrum", False),
    ("FLTrust", "fltrust", False),
    ("FedAvg + Fair", "fedavg", True),
    ("Multi-Krum + Fair", "multikrum", True),
    ("FLTrust + Fair", "fltrust", True),
    ("Sangam-Trust (no fairness)", "sangam", False),
    ("Sangam (full)", "sangam", True),
]
# scenario name -> (attack type, compromised bank ids)
#   minority: Large Private Bank + Small Finance Bank (~33% of data)
#   majority: 4 of 7 banks (~59% of data) - beyond what Krum/Median/Trimmed-Mean can tolerate
SCENARIOS = {
    "none": (None, ()),
    "label_flip": ("label_flip", (0, 3)),
    "sign_flip": ("sign_flip", (0, 3)),
    "label_flip_majority": ("label_flip", (0, 1, 3, 6)),
    "sign_flip_majority": ("sign_flip", (0, 1, 3, 6)),
    "targeted_senior": ("targeted_senior", (0, 3)),
    "targeted_senior_majority": ("targeted_senior", (0, 1, 3, 6)),
}

_DATA = {}


def _init(data_path, seed_list):
    import torch
    torch.set_num_threads(1)
    from sangam.data import build
    for s in seed_list:
        _DATA[s] = build(data_path, seed=s)


def _job(args):
    label, method, fair, scen, seed, rounds = args
    attack, malicious = SCENARIOS[scen]
    from sangam.fl import Config, run_federated, run_local, run_central
    import torch
    tr, te, pr, _ = _DATA[seed]
    cfg = Config(method=method, fair=fair, attack=attack, malicious=malicious, seed=seed, rounds=rounds)
    t = time.time()
    if method == "local":
        out = run_local(cfg, tr, te)
    elif method == "central":
        out = run_central(cfg, tr, te)
    else:
        out = run_federated(cfg, tr, te, pr)
    sd = out.pop("state_dict", None)
    if sd is not None and seed == 0:
        mdir = ROOT / "results" / "models"
        mdir.mkdir(parents=True, exist_ok=True)
        torch.save(sd, mdir / f"{method}{'_fair' if fair else ''}_{scen}.pt")
    return dict(label=label, method=method, fair=fair, attack=scen, malicious=list(malicious), seed=seed,
                seconds=round(time.time() - t, 1), **out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT.parent / "data" / "base.parquet"))
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--scenarios", nargs="+", default=None)
    ap.add_argument("--out", default=str(ROOT / "results" / "runs.jsonl"))
    a = ap.parse_args()

    jobs = []
    for seed in a.seeds:
        for scen in (a.scenarios or SCENARIOS):
            for label, method, fair in METHODS:
                if method in ("local", "central") and scen != "none":
                    continue  # attacks only make sense in a federation
                jobs.append((label, method, fair, scen, seed, a.rounds))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    print(f"{len(jobs)} runs on {a.workers} workers", flush=True)
    t0 = time.time()
    with open(a.out, "w") as f, get_context("spawn").Pool(a.workers, initializer=_init,
                                                          initargs=(a.data, a.seeds)) as pool:
        for i, res in enumerate(pool.imap_unordered(_job, jobs), 1):
            f.write(json.dumps(res) + "\n")
            f.flush()
            fin = res["final"]
            print(f"[{i}/{len(jobs)} {time.time()-t0:5.0f}s] {res['label']:<28} {res['attack']:<10} s{res['seed']} "
                  f"AUC={fin['auc']:.3f} TPR={fin['tpr']:.3f} FPRratio={fin['fpr_ratio']:.2f}", flush=True)


if __name__ == "__main__":
    main()
