"""Maps official challenge CSV columns to Fiducia fund schema."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = ROOT / "config" / "dataset_mapping.json"
OFFICIAL_DIR = ROOT / "data" / "official"


def load_mapping() -> dict[str, str]:
    with open(MAPPING_PATH) as f:
        return json.load(f)["column_map"]


def load_official_funds() -> list[dict[str, Any]]:
    """Load all CSVs from data/official/, map columns, return fund dicts. Blank != zero."""
    mapping = load_mapping()
    funds: list[dict[str, Any]] = []
    for csv_path in OFFICIAL_DIR.glob("*.csv"):
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        for _, row in df.iterrows():
            fund: dict[str, Any] = {}
            for col, field in mapping.items():
                if col in row.index:
                    raw = row[col].strip()
                    fund[field] = None if raw == "" else _coerce(field, raw)
            funds.append(fund)
    return funds


def _coerce(field: str, value: str) -> Any:
    numeric_fields = {"nav", "expense_ratio", "sharpe_ratio", "fee_12b1",
                      "distribution_12b1_fee", "service_fee", "sales_load_pct",
                      "turnover_rate", "aum_millions", "track_record_years", "risk_score"}
    if field in numeric_fields:
        try:
            return float(value)
        except ValueError:
            return value
    return value
