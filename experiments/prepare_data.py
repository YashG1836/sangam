"""Convert the BAF Base.csv (from Kaggle) into ../data/base.parquet used by all experiments."""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
a = ap.parse_args()
out = ROOT.parent / "data" / "base.parquet"
out.parent.mkdir(parents=True, exist_ok=True)
pd.read_csv(a.csv).to_parquet(out)
print("wrote", out)
