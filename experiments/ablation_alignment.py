"""Ablation: does the trust score need to use the fairness-weighted objective?
Sangam (full) with aligned vs unaligned trust scoring, under model poisoning. Writes results/ablation.jsonl."""
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
    align, scen, mal, seed = a
    from sangam.fl import Config, run_federated
    tr, te, pr, _ = _D[seed]
    out = run_federated(Config(method="sangam", fair=True, attack="sign_flip", malicious=mal, align_trust=align, seed=seed), tr, te, pr)
    ws = [h["weights"] for h in out["history"]]
    aw = sum(sum(w[i] for i in mal) for w in ws) / len(ws)
    return dict(align=align, attack=scen, seed=seed, attacker_weight=aw, final=out["final"])


if __name__ == "__main__":
    seeds = [0, 1, 2]
    jobs = [(al, sc, m, s) for al in (True, False) for sc, m in (("sign_flip", (0, 3)), ("sign_flip_majority", (0, 1, 3, 6))) for s in seeds]
    with open(ROOT / "results" / "ablation.jsonl", "w") as f, get_context("spawn").Pool(
            9, initializer=_init, initargs=(str(ROOT.parent / "data" / "base.parquet"), seeds)) as p:
        for r in p.imap_unordered(_job, jobs):
            f.write(json.dumps(r) + "\n"); f.flush()
            print(r["align"], r["attack"], r["seed"], round(r["final"]["tpr"], 3), round(r["attacker_weight"], 3), flush=True)
