"""Fairness / fraud-capture trade-off: sweep the cap on fairness weights (lambda_max) for
Sangam. lambda_max = 1 means fairness weighting is off. Writes results/sweep.jsonl."""
from __future__ import annotations

import json
import sys
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_D = {}


def _init(path, seeds):
    import torch
    torch.set_num_threads(1)
    from sangam.data import build
    for s in seeds:
        _D[s] = build(path, seed=s)


def _job(a):
    fm, scen, mal, atk, seed = a
    from sangam.fl import Config, run_federated
    tr, te, pr, _ = _D[seed]
    out = run_federated(Config(method="sangam", fair=fm > 1, fair_max=fm, attack=atk, malicious=mal, seed=seed),
                        tr, te, pr, log_every=30)
    out.pop("state_dict", None)
    return dict(fair_max=fm, attack=scen, seed=seed, final=out["final"])


if __name__ == "__main__":
    seeds = [0, 1, 2]
    jobs = [(fm, "none", (), None, s) for fm in (1.0, 1.5, 2.0, 3.0, 4.0, 6.0) for s in seeds]
    with open(ROOT / "results" / "sweep.jsonl", "w") as f, get_context("spawn").Pool(
            9, initializer=_init, initargs=(str(ROOT.parent / "data" / "base.parquet"), seeds)) as p:
        for r in p.imap_unordered(_job, jobs):
            f.write(json.dumps(r) + "\n")
            f.flush()
            print(r["fair_max"], r["seed"], round(r["final"]["tpr"], 3), round(r["final"]["fpr_ratio"], 2), flush=True)
