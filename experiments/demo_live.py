"""Live demo for the finale: actually trains the consortium on this laptop, round by round,
and prints what each defence does under a chosen attack. Takes about a minute.

    python experiments/demo_live.py --attack targeted_senior --majority
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402
from sangam.data import BANK_SHORT, build  # noqa: E402
from sangam.fl import Config, run_federated  # noqa: E402

RED, BLUE, DIM, BOLD, END = "\033[91m", "\033[94m", "\033[2m", "\033[1m", "\033[0m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attack", default="targeted_senior", choices=["none", "label_flip", "sign_flip", "targeted_senior"])
    ap.add_argument("--majority", action="store_true", help="4 of 7 banks compromised instead of 2")
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--methods", nargs="+", default=["fedavg", "sangam"])
    a = ap.parse_args()
    torch.set_num_threads(4)
    mal = (0, 1, 3, 6) if a.majority else (0, 3)
    attack = None if a.attack == "none" else a.attack
    print(f"{BOLD}Loading 1,000,000 applications and forming a 7-bank consortium...{END}")
    tr, te, pr, _ = build(ROOT.parent / "data" / "base.parquet")
    if attack:
        print(f"Compromised banks: {RED}{', '.join(BANK_SHORT[i] for i in mal)}{END}   attack: {attack}\n")
    for m in a.methods:
        fair = m == "sangam"
        print(f"{BOLD}{BLUE if fair else ''}== {('Sangam' if fair else m)} =={END}")
        out = run_federated(Config(method=m, fair=fair, attack=attack, malicious=mal if attack else (), rounds=a.rounds), tr, te, pr)
        for h in out["history"]:
            w = h["weights"]
            ws = " ".join((RED if (attack and i in mal) else DIM) + f"{BANK_SHORT[i]}:{100*w[i]:3.0f}%" + END for i in range(len(w))) if w else ""
            print(f"round {h['round']:2d}  fraud caught {100*h['tpr']:5.1f}%  senior fraud caught {100*h['tpr_senior']:5.1f}%  "
                  f"seniors wrongly flagged {100*h['fpr_senior']:4.1f}%   {ws}")
        print()


if __name__ == "__main__":
    main()
