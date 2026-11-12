"""Federated learning engine for the Sangam consortium.

Implements: local training with group-aware loss weights, two poisoning attacks,
baseline aggregators (FedAvg, coordinate-wise Median, Trimmed-Mean, Multi-Krum, FLTrust)
and the Sangam aggregator (group-aware trust scoring + adaptive fairness weighting).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import torch
from torch import nn
from sklearn.metrics import roc_auc_score

from .data import Split

TARGET_FPR = 0.05  # BAF operating point: at most 5% of genuine applicants flagged


# ----------------------------------------------------------------------------- model
class MLP(nn.Module):
    def __init__(self, d: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(d, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x):
        return self.net(x).squeeze(-1)


def get_vec(m: nn.Module) -> torch.Tensor:
    return torch.nn.utils.parameters_to_vector(m.parameters()).detach().clone()


def set_vec(m: nn.Module, v: torch.Tensor) -> None:
    torch.nn.utils.vector_to_parameters(v, m.parameters())


@torch.no_grad()
def predict(m: nn.Module, X: torch.Tensor, bs: int = 65536) -> np.ndarray:
    m.eval()
    return torch.cat([torch.sigmoid(m(X[i:i + bs])) for i in range(0, len(X), bs)]).numpy()


# ----------------------------------------------------------------------------- client
@dataclass
class ClientData:
    X: torch.Tensor
    y: torch.Tensor
    senior: torch.Tensor

    @classmethod
    def from_split(cls, s: Split, mask: np.ndarray | None = None) -> "ClientData":
        if mask is None:
            mask = np.ones(len(s.y), bool)
        return cls(torch.from_numpy(s.X[mask]), torch.from_numpy(s.y[mask]).float(),
                   torch.from_numpy(s.senior[mask]))

    def __len__(self):
        return len(self.y)


def sample_weights(y: torch.Tensor, senior: torch.Tensor, pos_weight: float, lam: dict) -> torch.Tensor:
    """Fraud cases get pos_weight; genuine applicants get a group-specific weight lam[g]
    (raised by the server for the group that is wrongly flagged too often)."""
    neg_w = torch.where(senior, torch.tensor(lam["senior"]), torch.tensor(lam["non_senior"]))
    return torch.where(y > 0.5, torch.tensor(pos_weight), neg_w)


def local_train(model: nn.Module, gvec: torch.Tensor, cd: ClientData, *, epochs: int, lr: float,
                batch: int, pos_weight: float, lam: dict, attack: str | None, gen: torch.Generator) -> torch.Tensor:
    set_vec(model, gvec.clone())
    model.train()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    y = cd.y
    if attack == "label_flip":           # data poisoning: compromised bank labels fraud as genuine and vice versa
        y = 1.0 - y
    w = sample_weights(y, cd.senior, pos_weight, lam)
    if attack == "targeted_senior":      # stealthy: only senior-citizen fraud is relabelled as genuine (and emphasised)
        tgt = cd.senior & (y > 0.5)
        y = torch.where(tgt, torch.zeros_like(y), y)
        w = torch.where(tgt, torch.full_like(w, 5.0 * pos_weight), w)
    n = len(y)
    for _ in range(epochs):
        perm = torch.randperm(n, generator=gen)
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            logits = model(cd.X[idx])
            loss = (nn.functional.binary_cross_entropy_with_logits(logits, y[idx], reduction="none") * w[idx]).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    delta = get_vec(model) - gvec
    if attack == "sign_flip":            # model poisoning: send a boosted update in the opposite direction
        delta = -4.0 * delta
    return delta


# ----------------------------------------------------------------------------- metrics
def threshold_at_fpr(scores: np.ndarray, y: np.ndarray, fpr: float = TARGET_FPR) -> float:
    return float(np.quantile(scores[y == 0], 1 - fpr))


def evaluate(scores: np.ndarray, s: Split, banks: list[int] | None = None) -> dict:
    y, sen = s.y, s.senior
    t = threshold_at_fpr(scores, y)
    flag = scores > t
    out = dict(auc=float(roc_auc_score(y, scores)), tpr=float(flag[y == 1].mean()), fpr=float(flag[y == 0].mean()))
    for g, m in (("senior", sen), ("non_senior", ~sen)):
        out[f"tpr_{g}"] = float(flag[(y == 1) & m].mean())
        out[f"fpr_{g}"] = float(flag[(y == 0) & m].mean())
    hi, lo = max(out["fpr_senior"], out["fpr_non_senior"]), min(out["fpr_senior"], out["fpr_non_senior"])
    out["fpr_ratio"] = lo / hi if hi > 0 else 1.0           # BAF "predictive equality" (1.0 = perfectly fair)
    out["wrongly_flagged_seniors_per_lakh"] = out["fpr_senior"] * 1e5
    if banks is not None:                                    # each bank operates at its own 5% FPR
        per = {}
        for b in banks:
            m = s.bank == b
            if (s.y[m] == 1).sum() == 0:
                continue
            tb = threshold_at_fpr(scores[m], s.y[m])
            per[int(b)] = float((scores[m][s.y[m] == 1] > tb).mean())
        out["bank_tpr"] = per
    return out


# ----------------------------------------------------------------------------- aggregators
def agg_fedavg(deltas, sizes, **_):
    w = torch.tensor(sizes, dtype=torch.float32)
    return (torch.stack(deltas) * (w / w.sum())[:, None]).sum(0), (w / w.sum()).tolist()


def agg_median(deltas, sizes, **_):
    return torch.stack(deltas).median(0).values, None


def agg_trimmed_mean(deltas, sizes, f=2, **_):
    D = torch.stack(deltas).sort(0).values
    return D[f:len(deltas) - f].mean(0), None


def agg_multikrum(deltas, sizes, f=2, **_):
    D = torch.stack(deltas)
    n = len(deltas)
    dist = torch.cdist(D, D) ** 2
    k = n - f - 2
    scores = torch.stack([dist[i][torch.arange(n) != i].sort().values[:k].sum() for i in range(n)])
    chosen = scores.argsort()[: n - f]
    sel = torch.zeros(n)
    sel[chosen] = 1.0 / len(chosen)
    return D[chosen].mean(0), sel.tolist()


def agg_fltrust(deltas, sizes, server_delta=None, **_):
    g0 = server_delta
    trust, normed = [], []
    for d in deltas:
        cos = torch.nn.functional.cosine_similarity(d, g0, dim=0)
        trust.append(max(float(cos), 0.0))
        normed.append(d * (g0.norm() / (d.norm() + 1e-12)))
    t = torch.tensor(trust)
    if t.sum() == 0:
        return torch.zeros_like(g0), t.tolist()
    t = t / t.sum()
    return (torch.stack(normed) * t[:, None]).sum(0), t.tolist()


@torch.no_grad()
def group_losses(model, vec, probe: ClientData, pos_weight, lam=None) -> dict:
    set_vec(model, vec)
    model.eval()
    logits = model(probe.X)
    w = sample_weights(probe.y, probe.senior, pos_weight, lam or {"senior": 1.0, "non_senior": 1.0})
    l = nn.functional.binary_cross_entropy_with_logits(logits, probe.y, reduction="none") * w
    return {"senior": float(l[probe.senior].mean()), "non_senior": float(l[~probe.senior].mean())}


def agg_sangam(deltas, sizes, model=None, gvec=None, probe=None, pos_weight=None, lam=None,
               tau=0.002, harm_tol=0.05, **_):
    """Fairness-aligned, group-aware trust.

    Each client update is test-applied to the current global model and scored on the
    server's small probe set, separately for every customer group, using the SAME
    fairness-weighted objective the clients are asked to optimise (lam). This alignment
    matters: scoring on an unweighted loss lets a sign-flipped update look "helpful"
    once fairness reweighting is switched on (observed in our pilot).

    score_i = max_g relative improvement for group g   (helps ANY segment -> trusted)
              set to 0 if it harms some group by more than harm_tol (crafted updates)
    Update magnitudes are clipped to the median norm so a boosted update cannot dominate.
    Because trust comes from the probe set, not from agreement between clients, the
    defence still works when a MAJORITY of participants is compromised."""
    lam = lam or {"senior": 1.0, "non_senior": 1.0}
    norms = torch.stack([d.norm() for d in deltas])
    cap = norms.median()
    clipped = [d * min(1.0, float(cap / (d.norm() + 1e-12))) for d in deltas]
    base = group_losses(model, gvec, probe, pos_weight, lam)
    scores = []
    for d in clipped:
        after = group_losses(model, gvec + d, probe, pos_weight, lam)
        imp = [(base[g] - after[g]) / base[g] for g in base]
        scores.append(0.0 if min(imp) < -harm_tol else max(max(imp) + tau, 0.0))
    s = torch.tensor(scores) * torch.tensor(sizes, dtype=torch.float32)
    if s.sum() == 0:
        return torch.zeros_like(gvec), [0.0] * len(deltas)
    s = s / s.sum()
    return (torch.stack(clipped) * s[:, None]).sum(0), s.tolist()


AGGREGATORS = dict(fedavg=agg_fedavg, median=agg_median, trimmed_mean=agg_trimmed_mean,
                   multikrum=agg_multikrum, fltrust=agg_fltrust, sangam=agg_sangam)


# ----------------------------------------------------------------------------- training loops
@dataclass
class Config:
    method: str = "fedavg"            # key of AGGREGATORS, or "local" / "central"
    fair: bool = False                # adaptive fairness weighting (server-coordinated DCA-FW)
    attack: str | None = None         # None | "label_flip" | "sign_flip" | "targeted_senior"
    malicious: tuple = (0, 3)
    rounds: int = 30
    epochs: int = 1
    lr: float = 1e-3
    batch: int = 1024
    pos_weight: float = 10.0
    fair_eta: float = 0.5
    fair_max: float = 6.0
    align_trust: bool = True          # score updates on the fairness-weighted objective (ablation: False)
    seed: int = 0
    history: list = field(default_factory=list)


def fairness_update(lam: dict, scores: np.ndarray, probe_split: Split, eta: float, lam_max: float) -> dict:
    """DCA-FW adapted to predictive equality: raise the weight of genuine applicants in the
    group with the higher false-positive rate on the probe set, multiplicatively."""
    t = threshold_at_fpr(scores, probe_split.y)
    neg = probe_split.y == 0
    f_s = max(float((scores[neg & probe_split.senior] > t).mean()), 1e-4)
    f_n = max(float((scores[neg & ~probe_split.senior] > t).mean()), 1e-4)
    r = math.log(f_s / f_n)
    lam = dict(lam)
    if r > 0:
        lam["senior"] = float(np.clip(lam["senior"] * math.exp(eta * r), 1.0, lam_max))
        lam["non_senior"] = float(np.clip(lam["non_senior"] * math.exp(-eta * r), 1.0, lam_max))
    else:
        lam["non_senior"] = float(np.clip(lam["non_senior"] * math.exp(-eta * r), 1.0, lam_max))
        lam["senior"] = float(np.clip(lam["senior"] * math.exp(eta * r), 1.0, lam_max))
    return lam


def run_federated(cfg: Config, train: Split, test: Split, probe: Split, log_every: int = 1) -> dict:
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(cfg.seed)
    d = train.X.shape[1]
    model = MLP(d)
    gvec = get_vec(model)
    n_banks = int(train.bank.max()) + 1
    clients = [ClientData.from_split(train, train.bank == b) for b in range(n_banks)]
    sizes = [len(c) for c in clients]
    probe_cd = ClientData.from_split(probe)
    Xte = torch.from_numpy(test.X)
    Xpr = torch.from_numpy(probe.X)
    lam = {"senior": 1.0, "non_senior": 1.0}
    honest = [b for b in range(n_banks) if not (cfg.attack and b in cfg.malicious)]
    agg = AGGREGATORS[cfg.method]
    hist = []
    for r in range(cfg.rounds):
        deltas = []
        for b, cd in enumerate(clients):
            atk = cfg.attack if (cfg.attack and b in cfg.malicious) else None
            deltas.append(local_train(model, gvec, cd, epochs=cfg.epochs, lr=cfg.lr, batch=cfg.batch,
                                      pos_weight=cfg.pos_weight, lam=lam, attack=atk, gen=gen))
        extra = {}
        if cfg.method == "fltrust":
            extra["server_delta"] = local_train(model, gvec, probe_cd, epochs=cfg.epochs, lr=cfg.lr, batch=256,
                                                pos_weight=cfg.pos_weight, lam=lam, attack=None, gen=gen)
        if cfg.method == "sangam":
            extra.update(model=model, gvec=gvec, probe=probe_cd, pos_weight=cfg.pos_weight,
                         lam=lam if cfg.align_trust else None)
        step, weights = agg(deltas, sizes, **extra)
        gvec = gvec + step
        set_vec(model, gvec.clone())
        if cfg.fair:
            lam = fairness_update(lam, predict(model, Xpr), probe, cfg.fair_eta, cfg.fair_max)
        if (r + 1) % log_every == 0 or r == cfg.rounds - 1:
            ev = evaluate(predict(model, Xte), test)
            hist.append(dict(round=r + 1, weights=weights, lam=dict(lam),
                             **{k: v for k, v in ev.items() if k != "bank_tpr"}))
    set_vec(model, gvec.clone())
    final = evaluate(predict(model, Xte), test, banks=honest)
    return dict(final=final, history=hist, state_dict={k: v.clone() for k, v in model.state_dict().items()})


def run_local(cfg: Config, train: Split, test: Split) -> dict:
    """Each bank trains alone on its own data (no collaboration). Same compute budget."""
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(cfg.seed)
    n_banks = int(train.bank.max()) + 1
    scores = np.zeros(len(test.y), dtype=np.float32)
    per = {}
    lam = {"senior": 1.0, "non_senior": 1.0}
    for b in range(n_banks):
        model = MLP(train.X.shape[1])
        cd = ClientData.from_split(train, train.bank == b)
        v = get_vec(model)
        v = v + local_train(model, v, cd, epochs=cfg.rounds * cfg.epochs, lr=cfg.lr, batch=cfg.batch,
                            pos_weight=cfg.pos_weight, lam=lam, attack=None, gen=gen)
        set_vec(model, v)
        m = test.bank == b
        sb = predict(model, torch.from_numpy(test.X[m]))
        scores[m] = sb
        tb = threshold_at_fpr(sb, test.y[m])
        per[b] = float((sb[test.y[m] == 1] > tb).mean())
    final = evaluate(scores, test)
    final["bank_tpr"] = per
    return dict(final=final, history=[])


def run_central(cfg: Config, train: Split, test: Split) -> dict:
    """Upper bound: all banks pool raw data in one place (not legally possible in practice)."""
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(cfg.seed)
    model = MLP(train.X.shape[1])
    cd = ClientData.from_split(train)
    v = get_vec(model)
    v = v + local_train(model, v, cd, epochs=min(cfg.rounds * cfg.epochs, 10), lr=cfg.lr, batch=cfg.batch,
                        pos_weight=cfg.pos_weight, lam={"senior": 1.0, "non_senior": 1.0}, attack=None, gen=gen)
    set_vec(model, v)
    final = evaluate(predict(model, torch.from_numpy(test.X)), test, banks=list(range(int(train.bank.max()) + 1)))
    return dict(final=final, history=[])
