"""Data loading, preprocessing and non-IID bank partitioning for the Sangam consortium.

Dataset: Bank Account Fraud (BAF) suite, Base variant (Jesus et al., NeurIPS 2022).
Each row is a bank-account-opening application; fraud_bool = 1 means the account was
opened fraudulently (the typical origin of a mule account).

Protocol follows the BAF paper: train on months 0-5, test on months 6-7,
operating point = 5% false-positive rate, protected attribute = customer_age >= 50.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CATEGORICAL = ["payment_type", "employment_status", "housing_status", "source", "device_os"]
DROP = ["fraud_bool", "month", "device_fraud_count"]  # device_fraud_count is constant in Base

# Simulated consortium members. Names are generic archetypes, not real institutions.
BANKS = [
    "Large Private Bank (Metro)",
    "Public Sector Bank (Pan-India)",
    "Digital Neobank",
    "Small Finance Bank",
    "Regional Rural Bank",
    "Urban Co-operative Bank",
    "IFSC Banking Unit (GIFT City)",
]
BANK_SHORT = ["PVT", "PSB", "NEO", "SFB", "RRB", "UCB", "IBU"]


@dataclass
class Split:
    X: np.ndarray          # float32 features
    y: np.ndarray          # int labels
    senior: np.ndarray     # bool, customer_age >= 50 (protected group)
    bank: np.ndarray       # int bank id


def load_raw(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def assign_banks(df: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Probabilistically assign each applicant to a bank so that every bank has a
    realistic, *different* customer mix (non-IID), e.g. the Regional Rural Bank and the
    Co-operative Bank serve older, lower-income customers; the Neobank serves the young."""
    age = df.customer_age.values
    inc = df.income.values
    young = (age <= 30).astype(float)
    senior = (age >= 50).astype(float)
    low_inc = (inc <= 0.3).astype(float)
    high_inc = (inc >= 0.8).astype(float)
    foreign = df.foreign_request.values.astype(float)
    teleapp = (df.source.to_numpy(dtype=object) == "TELEAPP").astype(float)
    mobile_os = np.isin(df.device_os.to_numpy(dtype=object), ["linux", "other"]).astype(float)

    prior = np.log(np.array([0.27, 0.31, 0.17, 0.10, 0.06, 0.05, 0.04]))
    logits = np.stack([
        prior[0] + 0.8 * high_inc - 0.6 * senior,                      # private metro
        prior[1] + 0.2 * senior + 0.2 * low_inc,                       # public sector
        prior[2] + 0.9 * young + 0.6 * mobile_os - 2.0 * senior,       # neobank
        prior[3] + 1.4 * low_inc - 0.3 * high_inc,                     # small finance
        prior[4] + 2.2 * senior + 1.0 * low_inc + 1.0 * teleapp - 1.5 * young,  # rural
        prior[5] + 1.8 * senior + 0.4 * teleapp - 1.0 * young,         # co-operative
        prior[6] + 3.0 * foreign + 1.0 * high_inc,                     # IFSC unit
    ], axis=1)
    p = np.exp(logits - logits.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    u = rng.random(len(df))[:, None]
    return (p.cumsum(1) < u).sum(1).clip(0, len(BANKS) - 1)


class Preprocessor:
    def fit(self, df: pd.DataFrame) -> "Preprocessor":
        feats = df.drop(columns=DROP)
        self.num_cols = [c for c in feats.columns if c not in CATEGORICAL]
        self.cats = {c: sorted(feats[c].unique().tolist()) for c in CATEGORICAL}
        num = feats[self.num_cols].astype(float)
        self.mu = num.mean().values
        self.sd = num.std().values + 1e-6
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        num = (df[self.num_cols].astype(float).values - self.mu) / self.sd
        oh = [(df[c].to_numpy(dtype=object)[:, None] == np.array(v, dtype=object)[None, :]).astype(float) for c, v in self.cats.items()]
        return np.concatenate([num] + oh, axis=1).astype(np.float32)

    @property
    def feature_names(self) -> list[str]:
        return self.num_cols + [f"{c}={v}" for c, vs in self.cats.items() for v in vs]


def build(path: str | Path, seed: int = 0, probe_frac: float = 0.02):
    """Returns (train, test, probe, preprocessor).

    probe: a small labelled reference set held by the consortium operator (e.g. a
    regulator sandbox or a hub such as RBIH). It is carved out of training months and is
    *never* trained on by clients; the server uses it only to score client updates.
    """
    rng = np.random.default_rng(seed)
    df = load_raw(path)
    df = df.assign(bank=assign_banks(df, rng))
    tr = df[df.month <= 5].reset_index(drop=True)
    te = df[df.month >= 6].reset_index(drop=True)
    pre = Preprocessor().fit(tr)

    probe_mask = rng.random(len(tr)) < probe_frac
    pr, tr = tr[probe_mask].reset_index(drop=True), tr[~probe_mask].reset_index(drop=True)

    def mk(d):
        return Split(pre.transform(d), d.fraud_bool.values.astype(np.int64),
                     (d.customer_age.values >= 50), d.bank.values.astype(np.int64))

    return mk(tr), mk(te), mk(pr), pre


def describe(train: Split) -> pd.DataFrame:
    rows = []
    for b, name in enumerate(BANKS):
        m = train.bank == b
        rows.append(dict(bank=name, applications=int(m.sum()),
                         share=float(m.mean()),
                         senior_share=float(train.senior[m].mean()),
                         fraud_rate=float(train.y[m].mean()),
                         fraud_cases=int(train.y[m].sum())))
    return pd.DataFrame(rows)
