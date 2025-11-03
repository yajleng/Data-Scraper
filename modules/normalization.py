# modules/normalization.py
import numpy as np
import pandas as pd

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
METRIC_COLS = [
    "epa_off",
    "epa_def",
    "success_rate_off",
    "success_rate_def",
    "explosiveness",
]

# ------------------------------------------------------------
# CORE NORMALIZATION FUNCTIONS
# ------------------------------------------------------------

def _zscore(series: pd.Series) -> pd.Series:
    """Safe z-score computation avoiding divide-by-zero errors."""
    mu = series.mean()
    sd = series.std(ddof=0)
    return (series - mu) / (sd if sd and sd > 0 else 1.0)


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: df with columns ['team', METRIC_COLS...]
    Output: DataFrame with *_z columns (z-scores) and composite_score.
    """
    df = df.copy()

    # Ensure numeric + fill missing with 0 for weekly consistency
    for col in METRIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Z-scores across all teams
    for col in METRIC_COLS:
        df[f"{col}_z"] = _zscore(df[col])

    # Composite score weights (tune as needed)
    # Offense ↑ good, defense ↓ good (inverted)
    df["composite_score"] = (
        0.30 * df["epa_off_z"]
        + 0.30 * df["success_rate_off_z"]
        + 0.10 * df["explosiveness_z"]
        + 0.20 * (-df["epa_def_z"])
        + 0.10 * (-df["success_rate_def_z"])
    )

    # Keep clean, sorted structure
    keep = ["team", "composite_score"] + [f"{c}_z" for c in METRIC_COLS]
    return df[keep].sort_values("composite_score", ascending=False).reset_index(drop=True)

# ------------------------------------------------------------
# COMPATIBILITY WRAPPER
# ------------------------------------------------------------

def preprocess_team_metrics(rows: list[dict]) -> list[dict]:
    """
    Compatibility wrapper for systems expecting preprocess_team_metrics().
    Converts list[dict] -> DataFrame -> normalized list[dict].
    """
    if not rows:
        return []

    df = pd.DataFrame(rows)
    if "team" not in df.columns:
        raise ValueError("Input must contain a 'team' field")

    return normalize_frame(df).to_dict(orient="records")

# ------------------------------------------------------------
# END OF FILE
# ------------------------------------------------------------
